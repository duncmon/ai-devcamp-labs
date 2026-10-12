// Server-side access to the ADK backend, wherever it happens to be running.
//
// The browser must never call the backend directly once it's deployed: Agent
// Runtime's `/api` passthrough is a Google API endpoint and needs a bearer
// token, which a browser has no safe way to hold. So every backend call is
// proxied through this Next.js server, which can mint one from ADC.
//
// Locally the backend is plain HTTP on localhost and needs no token at all,
// and this module transparently skips the auth in that case — so local dev
// behaves exactly as it did before the deployed backend existed.

import { GoogleAuth } from "google-auth-library";

/**
 * Origin of the ADK backend, WITHOUT a trailing slash and without the
 * `/api/adk` suffix — this is the root that `/api/posts` and `/outputs/...`
 * hang off.
 *
 *   local     http://localhost:8000
 *   deployed  https://<loc>-aiplatform.googleapis.com/reasoningEngines/v1/
 *             projects/<num>/locations/<loc>/reasoningEngines/<id>/api
 */
export const BACKEND_ORIGIN = (
  process.env.ADK_BACKEND_ORIGIN ?? "http://localhost:8000"
).replace(/\/+$/, "");

/**
 * This app's OWN AG-UI route (app/api/adk), which the CopilotKit runtime calls.
 * Server-to-self over loopback, so it never leaves the container. PORT is set
 * by Cloud Run; 3000 is Next's dev default.
 */
export const SELF_AGUI_URL = `http://127.0.0.1:${process.env.PORT ?? 3000}/api/adk`;

/** Google API endpoints need a token; a local backend does not. */
export const needsGoogleAuth = (url: string) =>
  /^https:\/\/[^/]*\.googleapis\.com\//.test(url);

// Resolves credentials from ADC: `gcloud auth application-default login`
// locally, or the attached service account on Cloud Run. getAccessToken()
// caches and refreshes internally, so minting per request is cheap and avoids
// the hour-long expiry a static header would hit.
const auth = new GoogleAuth({
  scopes: "https://www.googleapis.com/auth/cloud-platform",
});

export async function googleAuthHeader(): Promise<Record<string, string>> {
  const token = await (await auth.getClient()).getAccessToken();
  if (!token.token) {
    throw new Error(
      "No Google access token available. Run `gcloud auth application-default login`, " +
        "or deploy with a service account that has roles/aiplatform.user (see gcs-setup.sh).",
    );
  }
  return { Authorization: `Bearer ${token.token}` };
}

/** fetch() against the backend, adding auth only when the target needs it. */
export async function backendFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const url = `${BACKEND_ORIGIN}${path}`;
  const headers: Record<string, string> = {
    ...(init.headers as Record<string, string> | undefined),
    ...(needsGoogleAuth(url) ? await googleAuthHeader() : {}),
  };
  return fetch(url, { ...init, headers });
}
