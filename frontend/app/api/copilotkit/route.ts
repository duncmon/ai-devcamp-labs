import {
  CopilotRuntime,
  ExperimentalEmptyAdapter,
  copilotRuntimeNextJSAppRouterEndpoint,
} from "@copilotkit/runtime";
import { HttpAgent } from "@ag-ui/client";
import { NextRequest } from "next/server";

import { SELF_AGUI_URL } from "@/app/lib/backend";

// Bridges the browser to the ADK backend's AG-UI endpoint.
//
// Two backends are supported, and they differ only by env var:
//
//   local      ADK_BACKEND_ORIGIN=http://localhost:8000
//   deployed   ADK_BACKEND_ORIGIN=https://<loc>-aiplatform.googleapis.com/
//              reasoningEngines/v1/projects/<num>/locations/<loc>/
//              reasoningEngines/<id>/api
//
// The deployed form is Agent Runtime's `/api` passthrough, which exposes the
// container's own HTTP routes externally. Our container runs backend/main.py,
// which mounts AG-UI at /api/adk — hence the doubled `/api/api/`: the first
// is the passthrough prefix, the second is our own route. No protocol bridge
// is involved; the deployed engine speaks AG-UI directly.
// Points at this app's own /api/adk route, which adds the bearer token via
// backendFetch. Going through our own handler rather than HttpAgent's `fetch`
// option is deliberate: the override did not survive the production build, and
// the engine answered 401 UNAUTHENTICATED with the token missing.
const runtime = new CopilotRuntime({
  agents: {
    social_poster: new HttpAgent({ url: SELF_AGUI_URL }),
  },
});

export const POST = async (req: NextRequest) => {
  const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
    runtime,
    serviceAdapter: new ExperimentalEmptyAdapter(),
    endpoint: "/api/copilotkit",
  });
  return handleRequest(req);
};
