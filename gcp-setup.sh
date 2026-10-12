#!/usr/bin/env bash
# One-time manual GCP setup for this project — a growing checklist, not a
# single-purpose script. Every step below is written to be idempotent, so
# it's safe to re-run the whole file each time a new step is added rather
# than tracking which ones you've already done.
#
# Uses whichever Google account gcloud is logged in as (override with
# PERSONAL_EMAIL=you@gmail.com ./gcp-setup.sh). Needs GOOGLE_CLOUD_PROJECT in
# backend/social_poster/.env (copy .env.example there first), then run:
#   ./gcp-setup.sh
set -euo pipefail
cd "$(dirname "$0")"

# === Step 0: gcloud auth ====================================================
echo "=== Step 0: gcloud auth ==="
current_account="$(gcloud config get-value account 2>/dev/null || true)"
PERSONAL_EMAIL="${PERSONAL_EMAIL:-$current_account}"
if [[ -z "$PERSONAL_EMAIL" ]]; then
  echo "No gcloud account found. Run 'gcloud auth login', then re-run this script."
  exit 1
fi
echo "Using $PERSONAL_EMAIL."

ADC_FILE="$HOME/.config/gcloud/application_default_credentials.json"
if [[ -f "$ADC_FILE" ]]; then
  echo "Application Default Credentials already set up, skipping."
else
  gcloud auth application-default login
fi
echo

# Every step below needs the project; load it once, up front.
ENV_FILE="backend/social_poster/.env"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  source "$ENV_FILE"
  set +a
fi
if [[ -z "${GOOGLE_CLOUD_PROJECT:-}" ]]; then
  echo "GOOGLE_CLOUD_PROJECT is not set. Copy .env.example to $ENV_FILE and set it, then re-run."
  exit 1
fi

# Bill and quota-check API calls made with your ADC against this project.
# Without it, user ADC has no quota project: every SDK call warns "without a
# quota project", and some APIs (Cloud Trace reads, for one) reject or throttle
# the call against a shared Google-owned quota instead of yours.
current_quota="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('quota_project_id',''))" "$ADC_FILE" 2>/dev/null || true)"
if [[ "$current_quota" == "$GOOGLE_CLOUD_PROJECT" ]]; then
  echo "ADC quota project already $GOOGLE_CLOUD_PROJECT, skipping."
elif gcloud auth application-default set-quota-project "$GOOGLE_CLOUD_PROJECT" >/dev/null 2>&1; then
  echo "Set ADC quota project to $GOOGLE_CLOUD_PROJECT."
else
  echo "Could not set the ADC quota project (needs serviceusage.services.use on"
  echo "$GOOGLE_CLOUD_PROJECT). Continuing; SDK calls will warn about a missing quota project."
fi
echo

# === Step 1: GCS image hosting for Buffer (signed URLs, no key file) =======
# Lets Buffer posts carry an image, via a signed URL rather than a public
# bucket grant (Public Access Prevention blocks that outright on managed
# projects — see docs/LEARNINGS.md). Optional: not part of Lab 1's taught
# steps, which keep Buffer text-only by design. Skipped entirely if
# GCS_BUCKET_NAME isn't set in backend/social_poster/.env yet.
echo "=== Step 1: GCS image hosting for Buffer ==="
if [[ ! -f "$ENV_FILE" ]]; then
  echo "skipping — $ENV_FILE not found (copy .env.example there first)."
else
  if [[ -z "${GCS_BUCKET_NAME:-}" ]]; then
    echo "skipping — GCS_BUCKET_NAME not set in $ENV_FILE."
  else
    SA_NAME="social-spark-uploader"
    SA_EMAIL="${SA_NAME}@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com"

    echo "Project:     $GOOGLE_CLOUD_PROJECT"
    echo "Bucket:      $GCS_BUCKET_NAME"
    echo "Uploader SA: $SA_EMAIL"

    # Bucket names are global, so pick one with your project ID in it.
    # Private by default (Public Access Prevention on); us-central1 to sit
    # next to the deployed agent.
    if gcloud storage buckets describe "gs://$GCS_BUCKET_NAME" >/dev/null 2>&1; then
      echo "0/3  Bucket already exists, skipping create."
    else
      echo "0/3  Creating gs://$GCS_BUCKET_NAME..."
      gcloud storage buckets create "gs://$GCS_BUCKET_NAME" \
        --project="$GOOGLE_CLOUD_PROJECT" \
        --location=us-central1 \
        --uniform-bucket-level-access \
        --public-access-prevention >/dev/null
    fi

    if gcloud iam service-accounts describe "$SA_EMAIL" --project="$GOOGLE_CLOUD_PROJECT" >/dev/null 2>&1; then
      echo "1/3  Service account already exists, skipping create."
    else
      echo "1/3  Creating service account..."
      gcloud iam service-accounts create "$SA_NAME" \
        --project="$GOOGLE_CLOUD_PROJECT" \
        --display-name="Social Spark image uploader (signs GCS URLs, never downloads a key)"
    fi

    echo "2/3  Granting $SA_EMAIL write access to gs://$GCS_BUCKET_NAME..."
    gcloud storage buckets add-iam-policy-binding "gs://$GCS_BUCKET_NAME" \
      --member="serviceAccount:$SA_EMAIL" \
      --role="roles/storage.objectAdmin" >/dev/null

    echo "3/3  Granting $PERSONAL_EMAIL permission to impersonate $SA_EMAIL..."
    gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
      --project="$GOOGLE_CLOUD_PROJECT" \
      --member="user:$PERSONAL_EMAIL" \
      --role="roles/iam.serviceAccountTokenCreator" >/dev/null

    if grep -q "^GCS_SIGNING_SERVICE_ACCOUNT=" "$ENV_FILE"; then
      # macOS/BSD sed needs an explicit (empty) backup extension for -i.
      sed -i.bak "s|^GCS_SIGNING_SERVICE_ACCOUNT=.*|GCS_SIGNING_SERVICE_ACCOUNT=$SA_EMAIL|" "$ENV_FILE"
      rm -f "$ENV_FILE.bak"
      echo "Updated GCS_SIGNING_SERVICE_ACCOUNT in $ENV_FILE."
    else
      echo "Add this line to $ENV_FILE:"
      echo "  GCS_SIGNING_SERVICE_ACCOUNT=$SA_EMAIL"
    fi

    # === Step 1b: (optional) make the bucket public instead of signing =====
    # Off by default: signed URLs above are the taught path, and this
    # bucket has Public Access Prevention (PAP) enforced by default
    # specifically to block this (see docs/LEARNINGS.md — a plain
    # allUsers:objectViewer grant 412s outright while PAP is on). Opt in
    # with GCS_PUBLIC_BUCKET=true in $ENV_FILE only after you've turned
    # PAP off yourself (Console → bucket → Permissions → Public access
    # prevention → Inherit from project — a deliberate, human decision
    # this script won't make for you). Every image ever uploaded becomes
    # world-readable to anyone with the URL; know that before opting in.
    if [[ "${GCS_PUBLIC_BUCKET:-false}" == "true" ]]; then
      echo "1b/1  GCS_PUBLIC_BUCKET=true — checking Public Access Prevention..."
      pap="$(gcloud storage buckets describe "gs://$GCS_BUCKET_NAME" --format="value(public_access_prevention)")"
      if [[ "$pap" == "enforced" ]]; then
        echo "Public Access Prevention is still 'enforced' on gs://$GCS_BUCKET_NAME."
        echo "Turn it off first: Console → Cloud Storage → $GCS_BUCKET_NAME →"
        echo "Permissions → Public access prevention → Inherit from project."
        echo "Then re-run this script. Skipping the public grant for now."
      else
        echo "PAP is '$pap' — granting allUsers objectViewer on gs://$GCS_BUCKET_NAME..."
        gcloud storage buckets add-iam-policy-binding "gs://$GCS_BUCKET_NAME" \
          --member="allUsers" \
          --role="roles/storage.objectViewer" >/dev/null
        echo "Bucket is now public. Every object under gs://$GCS_BUCKET_NAME is"
        echo "readable by anyone with its URL, indefinitely — including images"
        echo "already uploaded before this step ran."
      fi
    fi
  fi
fi
echo

# === Step 2: APIs needed for Agent Runtime deploys ==========================
# `agents-cli deploy -d agent_runtime` fails without Cloud Resource Manager,
# and not with a helpful message — it surfaces as a 403 SERVICE_DISABLED from
# deep inside a gRPC stack trace. The rest are needed because Agent Runtime
# builds a container image from this repo's Dockerfile.
echo "=== Step 2: APIs for Agent Runtime ==="
gcloud services enable \
  cloudresourcemanager.googleapis.com \
  aiplatform.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  run.googleapis.com \
  secretmanager.googleapis.com \
  --project="$GOOGLE_CLOUD_PROJECT" >/dev/null
echo "Enabled (or already enabled)."
echo

# === Step 3: permission to call a deployed agent ============================
# A deployed agent is reached through Agent Runtime's `/api` passthrough
# (https://LOCATION-aiplatform.googleapis.com/reasoningEngines/v1/.../api/...),
# which is a Google API endpoint and needs a bearer token with the right role.
# Project owners have this implicitly, which is an easy way to not notice the
# requirement until someone with narrower access hits a 403.
echo "=== Step 3: aiplatform.user for calling deployed agents ==="
gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
  --member="user:$PERSONAL_EMAIL" \
  --role="roles/aiplatform.user" \
  --condition=None >/dev/null
echo "Granted roles/aiplatform.user to $PERSONAL_EMAIL."
echo

# === Step 4: service account for the deployed frontend ======================
# The frontend calls the passthrough server-side (frontend/app/api/copilotkit/
# route.ts mints a token from ADC), so when it runs on Cloud Run it needs its
# own identity with the same role. Locally this step is unnecessary — ADC is
# already your own account, covered by Step 3.
echo "=== Step 4: Cloud Run frontend service account ==="
FE_SA_NAME="social-spark-frontend"
FE_SA_EMAIL="$FE_SA_NAME@$GOOGLE_CLOUD_PROJECT.iam.gserviceaccount.com"
if gcloud iam service-accounts describe "$FE_SA_EMAIL" --project="$GOOGLE_CLOUD_PROJECT" >/dev/null 2>&1; then
  echo "Service account $FE_SA_EMAIL already exists, skipping create."
else
  gcloud iam service-accounts create "$FE_SA_NAME" \
    --project="$GOOGLE_CLOUD_PROJECT" \
    --display-name="Social Spark frontend (Cloud Run)" >/dev/null
  echo "Created $FE_SA_EMAIL."
fi
gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
  --member="serviceAccount:$FE_SA_EMAIL" \
  --role="roles/aiplatform.user" \
  --condition=None >/dev/null
echo "Granted roles/aiplatform.user to $FE_SA_EMAIL."
echo "Deploy the frontend with:  --service-account=$FE_SA_EMAIL"
echo

# === Step 5: Buffer API key in Secret Manager ==============================
# Buffer is what lets the agent post to X (and anything else you connect) —
# the local LinkedIn MCP server only does LinkedIn. A deployed agent therefore
# needs the Buffer token, and it must go through Secret Manager: passing it as
# a plain env var leaves it readable in clear text in the console.
#
# The key is read straight out of backend/social_poster/.env here, so it never
# gets pasted into a shell history or a chat window.
echo "=== Step 5: Buffer API key secret ==="
BUFFER_SECRET_ID="buffer-api-key"
if ! [[ -f "$ENV_FILE" ]]; then
  echo "No $ENV_FILE yet — skipping (create it, then re-run)."
elif gcloud secrets describe "$BUFFER_SECRET_ID" --project="$GOOGLE_CLOUD_PROJECT" >/dev/null 2>&1; then
  echo "Secret $BUFFER_SECRET_ID already exists, skipping create."
else
  buffer_key="$(grep -m1 "^BUFFER_API_KEY=" "$ENV_FILE" | cut -d= -f2- | tr -d "\r\n\"'" || true)"
  if [[ -z "$buffer_key" ]]; then
    echo "BUFFER_API_KEY not set in $ENV_FILE — skipping."
  else
    printf %s "$buffer_key" | gcloud secrets create "$BUFFER_SECRET_ID" \
      --project="$GOOGLE_CLOUD_PROJECT" --data-file=- >/dev/null
    echo "Created secret $BUFFER_SECRET_ID."
  fi
  unset buffer_key
fi

# Two grants, both up front (see docs/LEARNINGS.md):
# - The Agent Identity principalSet is what actually reads the secret: the
#   deployed agent gets only the secret's *name* (BUFFER_API_KEY_SECRET) and
#   fetches the value at runtime. It's the project-wide principalSet, not one
#   agent's principal, because that principal doesn't exist until after the
#   first successful deploy (a real chicken-and-egg).
# - The platform-managed Agent Engine service agent, which a Secret Manager
#   reference in the deployment spec itself would need. Harmless to have.
# Don't use `agents-cli deploy --secrets`: a container-based deployment rejects
# it with an opaque "The Reasoning Engine failed to be updated".
if gcloud secrets describe "$BUFFER_SECRET_ID" --project="$GOOGLE_CLOUD_PROJECT" >/dev/null 2>&1; then
  PROJECT_NUMBER="$(gcloud projects describe "$GOOGLE_CLOUD_PROJECT" --format='value(projectNumber)')"
  gcloud secrets add-iam-policy-binding "$BUFFER_SECRET_ID" \
    --project="$GOOGLE_CLOUD_PROJECT" \
    --member="principalSet://agents.global.proj-$PROJECT_NUMBER.system.id.goog/attribute.platformContainer/aiplatform/projects/$PROJECT_NUMBER" \
    --role="roles/secretmanager.secretAccessor" >/dev/null
  echo "Granted secretAccessor to this project's Agent Identity principals."
  gcloud secrets add-iam-policy-binding "$BUFFER_SECRET_ID" \
    --project="$GOOGLE_CLOUD_PROJECT" \
    --member="serviceAccount:service-$PROJECT_NUMBER@gcp-sa-aiplatform-re.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor" >/dev/null
  echo "Granted secretAccessor to the Agent Engine service agent."
  echo "Deploy the agent with the secret's name, not --secrets:"
  echo "  --update-env-vars \"POST_VIA=buffer,BUFFER_API_KEY_SECRET=$BUFFER_SECRET_ID,BUFFER_REVIEW_DELAY_MINUTES=60\""
fi
echo

# === Step 6: deployed agent can write published posts to GCS ===============
# A container's filesystem is wiped on every scale-to-zero, so the deployed
# agent keeps published posts in GCS (db.py switches when GCS_BUCKET_NAME is
# set) and writes them as its own Agent Identity. Same project-wide
# principalSet as Step 5, for the same chicken-and-egg reason.
echo "=== Step 6: GCS write access for deployed agents ==="
if [[ -z "${GCS_BUCKET_NAME:-}" ]]; then
  echo "skipping — GCS_BUCKET_NAME not set in $ENV_FILE."
else
  PROJECT_NUMBER="${PROJECT_NUMBER:-$(gcloud projects describe "$GOOGLE_CLOUD_PROJECT" --format='value(projectNumber)')}"
  gcloud storage buckets add-iam-policy-binding "gs://$GCS_BUCKET_NAME" \
    --member="principalSet://agents.global.proj-$PROJECT_NUMBER.system.id.goog/attribute.platformContainer/aiplatform/projects/$PROJECT_NUMBER" \
    --role="roles/storage.objectAdmin" >/dev/null
  echo "Granted storage.objectAdmin on gs://$GCS_BUCKET_NAME to this project's Agent Identity principals."
  echo "Deploy the agent with:  --update-env-vars \"GCS_BUCKET_NAME=$GCS_BUCKET_NAME\""
fi
echo

# === Step 7: (add the next one-time manual GCP step here) ==================

echo "Done."
