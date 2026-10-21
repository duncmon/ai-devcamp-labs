import { backendFetch, BACKEND_ORIGIN, needsGoogleAuth } from "@/app/lib/backend";

// Same-origin AG-UI endpoint proxying requests to the configured ADK backend.
//
// Enforces Principle 1 (Fail-Closed Diagnostics):
// When upstream endpoints are unreachable (ECONNREFUSED) or return HTTP 404
// (e.g. torn-down or deleted Vertex AI Reasoning Engine), synthesize a clean
// AG-UI Server-Sent Event (SSE) stream returning actionable Markdown diagnostic
// instructions rather than crashing CopilotKit with unhandled exceptions.
export const dynamic = "force-dynamic";

function makeDiagnosticEventStream(
  threadId: string,
  runId: string,
  markdownMessage: string,
): Response {
  const messageId = `diag-${Date.now()}`;
  const events = [
    { type: "RUN_STARTED", threadId, runId },
    { type: "TEXT_MESSAGE_START", messageId, role: "assistant" },
    { type: "TEXT_MESSAGE_CONTENT", messageId, delta: markdownMessage },
    { type: "TEXT_MESSAGE_END", messageId },
    { type: "RUN_FINISHED", threadId, runId },
  ];

  const sseBody = events
    .map((evt) => `data: ${JSON.stringify(evt)}\n\n`)
    .join("");

  return new Response(sseBody, {
    status: 200,
    headers: {
      "content-type": "text/event-stream; charset=utf-8",
      "cache-control": "no-store, no-cache, must-revalidate",
      connection: "keep-alive",
    },
  });
}

export async function POST(req: Request) {
  let threadId = `thread-${Date.now()}`;
  let runId = `run-${Date.now()}`;
  let requestText = "";

  try {
    requestText = await req.text();
    if (requestText) {
      const parsed = JSON.parse(requestText);
      if (parsed.threadId && typeof parsed.threadId === "string") {
        threadId = parsed.threadId;
      }
      if (parsed.runId && typeof parsed.runId === "string") {
        runId = parsed.runId;
      }
    }
  } catch {
    // Non-JSON or empty payload; retain generated default IDs
  }

  const isRemote = needsGoogleAuth(BACKEND_ORIGIN);

  try {
    const upstream = await backendFetch("/api/adk", {
      method: "POST",
      headers: {
        "content-type": req.headers.get("content-type") ?? "application/json",
        accept: req.headers.get("accept") ?? "text/event-stream",
      },
      body: requestText,
      // @ts-expect-error -- Node's fetch needs this to stream a response body.
      duplex: "half",
    });

    if (upstream.status === 404) {
      const diag = isRemote
        ? `⚠️ **Vertex AI Reasoning Engine Endpoint Not Found (HTTP 404)**\n\n` +
          `The configured cloud backend is unreachable:\n` +
          `\`${BACKEND_ORIGIN}\`\n\n` +
          `**Probable Causes:**\n` +
          `- The Reasoning Engine was deleted, expired, or torn down.\n` +
          `- Stale \`deployment_metadata.json\` or outdated \`.env.local\`.\n\n` +
          `**Resolution Steps:**\n` +
          `1. **Switch to Local Development:**\n` +
          `   \`\`\`bash\n` +
          `   ./run-backend.sh\n` +
          `   ./run-frontend.sh --local\n` +
          `   \`\`\`\n` +
          `2. **Deploy Fresh Cloud Engine:**\n` +
          `   \`\`\`bash\n` +
          `   agents-cli deploy\n` +
          `   ./run-frontend.sh --cloud\n` +
          `   \`\`\``
        : `⚠️ **Local ADK Endpoint Not Found (HTTP 404)**\n\n` +
          `Backend returned 404 at \`${BACKEND_ORIGIN}/api/adk\`.\n\n` +
          `**Probable Causes:**\n` +
          `- The service on port 8000 is not running the Social Spark backend.\n` +
          `- The AG-UI route \`/api/adk\` is not mounted.\n\n` +
          `**Resolution Steps:**\n` +
          `1. Restart the local backend:\n` +
          `   \`\`\`bash\n` +
          `   ./run-backend.sh\n` +
          `   \`\`\`\n` +
          `2. Check backend startup logs to confirm \`/api/adk\` is mounted.`;

      return makeDiagnosticEventStream(threadId, runId, diag);
    }

    if (upstream.status === 429) {
      const diag = isRemote
        ? `⚠️ **Vertex AI Capacity Temporarily Exhausted (HTTP 429 RESOURCE_EXHAUSTED)**\n\n` +
          `Google Cloud Vertex AI reported that regional shared model capacity in \`us-central1\` ` +
          `is temporarily exhausted under current burst demand.\n\n` +
          `**Probable Causes:**\n` +
          `- Burst of concurrent requests across multi-agent loops (researcher, drafter, orchestrator).\n` +
          `- Shared regional quotas on Gemini 2.5 models.\n\n` +
          `**Resolution Steps:**\n` +
          `1. **Wait and Retry:** Wait 5–10 seconds and submit your prompt again (ADK automatic exponential backoff with jitter will smooth subsequent requests).\n` +
          `2. **Switch to Local Development:**\n` +
          `   \`\`\`bash\n` +
          `   ./run-backend.sh\n` +
          `   ./run-frontend.sh --local\n` +
          `   \`\`\`\n` +
          `3. **Reference:** Learn more at [Google ADK Gemini Rate Limits](https://google.github.io/adk-docs/agents/models/google-gemini/#error-code-429-resource_exhausted).`
        : `⚠️ **Local Rate Limit Exceeded (HTTP 429)**\n\n` +
          `Rate limit exceeded. Please wait a moment and try again.`;

      return makeDiagnosticEventStream(threadId, runId, diag);
    }

    if (upstream.status === 401 || upstream.status === 403) {
      const diag = isRemote
        ? `⚠️ **Vertex AI Authentication / Permission Error (HTTP ${upstream.status})**\n\n` +
          `Authentication to Google Cloud failed for:\n` +
          `\`${BACKEND_ORIGIN}\`\n\n` +
          `**Probable Causes:**\n` +
          `- Expired or invalid Application Default Credentials (ADC).\n` +
          `- The active account lacks \`roles/aiplatform.user\` permissions.\n\n` +
          `**Resolution Steps:**\n` +
          `1. Re-authenticate with Google Cloud:\n` +
          `   \`\`\`bash\n` +
          `   gcloud auth application-default login\n` +
          `   \`\`\`\n` +
          `2. Or switch to local development:\n` +
          `   \`\`\`bash\n` +
          `   ./run-backend.sh\n` +
          `   ./run-frontend.sh --local\n` +
          `   \`\`\``
        : `⚠️ **Local Backend Authentication Error (HTTP ${upstream.status})**\n\n` +
          `Local backend rejected request with HTTP ${upstream.status}.`;

      return makeDiagnosticEventStream(threadId, runId, diag);
    }

    if (!upstream.ok) {
      const diag = `⚠️ **Backend Service Error (HTTP ${upstream.status})**\n\n` +
        `The backend at \`${BACKEND_ORIGIN}\` returned status code ${upstream.status}.\n\n` +
        `**Resolution Steps:**\n` +
        `1. Check the backend terminal console for tracebacks or exception logs.\n` +
        `2. If running locally, check \`./run-backend.sh\` output.\n` +
        `3. If running in cloud mode, verify Reasoning Engine status in Google Cloud Console.`;

      return makeDiagnosticEventStream(threadId, runId, diag);
    }

    // Intercept in-stream fatal errors (e.g. agent_run_error_event with 429 RESOURCE_EXHAUSTED)
    // so CopilotKit renders a clean diagnostic card rather than an unhandled modal error crash.
    let responseBody = upstream.body;
    const contentType = upstream.headers.get("content-type") ?? "";
    if (upstream.body && contentType.includes("text/event-stream")) {
      const decoder = new TextDecoder();
      const encoder = new TextEncoder();
      let buffer = "";

      const transform = new TransformStream({
        transform(chunk, controller) {
          buffer += decoder.decode(chunk, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const dataStr = line.slice(6).trim();
              if (
                dataStr &&
                (dataStr.includes("agent_run_error_event") ||
                  dataStr.includes("RESOURCE_EXHAUSTED"))
              ) {
                try {
                  const messageId = `diag-${Date.now()}`;
                  const diagMsg = isRemote
                    ? `⚠️ **Vertex AI Capacity Temporarily Exhausted (HTTP 429 RESOURCE_EXHAUSTED)**\n\n` +
                      `Google Cloud Vertex AI reported that regional shared model capacity in \`us-central1\` ` +
                      `is temporarily exhausted under current burst demand.\n\n` +
                      `**Resolution Steps:**\n` +
                      `1. **Wait and Retry:** Wait 5–10 seconds and submit your prompt again (ADK automatic exponential backoff with jitter will smooth subsequent requests).\n` +
                      `2. **Switch to Local Development:**\n` +
                      `   \`\`\`bash\n` +
                      `   ./run-backend.sh\n` +
                      `   ./run-frontend.sh --local\n` +
                      `   \`\`\`\n` +
                      `3. **Reference:** Learn more at [Google ADK Gemini Rate Limits](https://google.github.io/adk-docs/agents/models/google-gemini/#error-code-429-resource_exhausted).`
                    : `⚠️ **Rate Limit Exceeded (HTTP 429)**\n\nPlease wait a moment and try again.`;

                  controller.enqueue(
                    encoder.encode(
                      `data: ${JSON.stringify({
                        type: "TEXT_MESSAGE_START",
                        messageId,
                        role: "assistant",
                      })}\n\n`,
                    ),
                  );
                  controller.enqueue(
                    encoder.encode(
                      `data: ${JSON.stringify({
                        type: "TEXT_MESSAGE_CONTENT",
                        messageId,
                        delta: diagMsg,
                      })}\n\n`,
                    ),
                  );
                  controller.enqueue(
                    encoder.encode(
                      `data: ${JSON.stringify({
                        type: "TEXT_MESSAGE_END",
                        messageId,
                      })}\n\n`,
                    ),
                  );
                  controller.enqueue(
                    encoder.encode(
                      `data: ${JSON.stringify({
                        type: "RUN_FINISHED",
                        threadId,
                        runId,
                      })}\n\n`,
                    ),
                  );
                  continue;
                } catch {
                  // Fall through to emit raw line on parse error
                }
              }
            }
            controller.enqueue(encoder.encode(line + "\n"));
          }
        },
        flush(controller) {
          if (buffer) {
            controller.enqueue(encoder.encode(buffer));
          }
        },
      });

      responseBody = upstream.body.pipeThrough(transform);
    }

    return new Response(responseBody, {
      status: upstream.status,
      headers: {
        "content-type":
          upstream.headers.get("content-type") ?? "text/event-stream",
        "cache-control": "no-store",
        connection: "keep-alive",
      },
    });
  } catch (err: any) {
    const isConnRefused =
      err?.code === "ECONNREFUSED" ||
      err?.cause?.code === "ECONNREFUSED" ||
      err?.message?.includes("ECONNREFUSED") ||
      err?.message?.includes("fetch failed");

    const diag = isRemote
      ? `⚠️ **Vertex AI Connection Failure**\n\n` +
        `Failed to establish connection to \`${BACKEND_ORIGIN}\`.\n\n` +
        `**Error:** \`${err?.message ?? "Network connection error"}\`\n\n` +
        `**Resolution Steps:**\n` +
        `1. Ensure Google Cloud credentials are valid: \`gcloud auth application-default login\`\n` +
        `2. Check network connectivity and Reasoning Engine deployment status.\n` +
        `3. To switch to local development: \`./run-backend.sh\` and \`./run-frontend.sh --local\``
      : `⚠️ **Local Backend Unreachable**\n\n` +
        `Cannot connect to local backend at \`${BACKEND_ORIGIN}\`${isConnRefused ? " (Connection refused)" : ""}.\n\n` +
        `**Probable Causes:**\n` +
        `- The backend service is not running on port 8000.\n\n` +
        `**Resolution Steps:**\n` +
        `1. Start the local backend:\n` +
        `   \`\`\`bash\n` +
        `   ./run-backend.sh\n` +
        `   \`\`\`\n` +
        `2. Or switch to cloud mode:\n` +
        `   \`\`\`bash\n` +
        `   ./run-frontend.sh --cloud\n` +
        `   \`\`\``;

    return makeDiagnosticEventStream(threadId, runId, diag);
  }
}
