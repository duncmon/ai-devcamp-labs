#!/usr/bin/env bash
# Dynamic, Idempotent Setup of Cloud Build Eval-Gate Prerequisites
# Resolves active GCP identities dynamically to satisfy production standards.

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}======================================================================${NC}"
echo -e "${YELLOW}🔍 Resolving Active Google Cloud Environment & Identities...${NC}"
echo -e "${BLUE}======================================================================${NC}"

# Respect isolated direnv configuration if not already exported in subshell
if [ -z "${CLOUDSDK_ACTIVE_CONFIG_NAME:-}" ]; then
  export CLOUDSDK_ACTIVE_CONFIG_NAME="ai-devcamp"
fi

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-}"
if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" = "(unset)" ]; then
  PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
fi
if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" = "(unset)" ]; then
  PROJECT_ID="ai-devcamp-duncan-395792"
fi

echo -e "Project ID:      ${GREEN}${PROJECT_ID}${NC}"

PROJECT_NUM=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
echo -e "Project Number:  ${GREEN}${PROJECT_NUM}${NC}"

CB_SA="${PROJECT_NUM}@cloudbuild.gserviceaccount.com"
echo -e "Cloud Build SA:  ${GREEN}${CB_SA}${NC}"

REGION="${_REGION:-us-central1}"
echo -e "Target Region:   ${GREEN}${REGION}${NC}"

LOGS_BUCKET="gs://${PROJECT_ID}-cloudbuild-logs"

echo -e "\n${BLUE}======================================================================${NC}"
echo -e "${YELLOW}📦 1. Provisioning Cloud Storage Logs Bucket (${LOGS_BUCKET})...${NC}"
echo -e "${BLUE}======================================================================${NC}"

if gcloud storage buckets describe "$LOGS_BUCKET" >/dev/null 2>&1; then
  echo -e "${GREEN}Bucket ${LOGS_BUCKET} already exists.${NC}"
else
  echo -e "Creating bucket ${LOGS_BUCKET} in ${REGION}..."
  gcloud storage buckets create "$LOGS_BUCKET" --location="$REGION" --project="$PROJECT_ID"
  echo -e "${GREEN}Bucket ${LOGS_BUCKET} created successfully.${NC}"
fi

echo -e "\n${BLUE}======================================================================${NC}"
echo -e "${YELLOW}🔐 2. Provisioning Secret Manager Secret (model-armor-template-id)...${NC}"
echo -e "${BLUE}======================================================================${NC}"

if gcloud secrets describe model-armor-template-id --project="$PROJECT_ID" >/dev/null 2>&1; then
  echo -e "${GREEN}Secret model-armor-template-id already exists.${NC}"
else
  echo -e "Creating secret model-armor-template-id..."
  echo -n "devcamp-guardrails" | gcloud secrets create model-armor-template-id \
    --data-file=- \
    --replication-policy=automatic \
    --project="$PROJECT_ID"
  echo -e "${GREEN}Secret model-armor-template-id created with template value 'devcamp-guardrails'.${NC}"
fi

echo -e "\n${BLUE}======================================================================${NC}"
echo -e "${YELLOW}🛡️ 3. Granting Required IAM Roles to Cloud Build Service Account...${NC}"
echo -e "${BLUE}======================================================================${NC}"

REQUIRED_ROLES=(
  "roles/aiplatform.user"
  "roles/secretmanager.secretAccessor"
  "roles/run.admin"
  "roles/iam.serviceAccountUser"
)

for ROLE in "${REQUIRED_ROLES[@]}"; do
  echo -e "Ensuring role binding: ${ROLE} -> ${CB_SA}..."
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${CB_SA}" \
    --role="$ROLE" \
    --condition=None \
    --quiet >/dev/null
  echo -e "${GREEN}Binding verified: ${ROLE}${NC}"
done

echo -e "\n${BLUE}======================================================================${NC}"
echo -e "${GREEN}✅ All Cloud Build Eval-Gate Prerequisites Successfully Provisioned.${NC}"
echo -e "${BLUE}======================================================================${NC}"
