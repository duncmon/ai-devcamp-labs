import { backendFetch } from "@/app/lib/backend";

// Same-origin AG-UI endpoint.
//
// The CopilotKit runtime's HttpAgent points here rather than straight at the
// backend, so the outbound call goes through backendFetch — the same code path
// /api/posts uses, which is proven to authenticate correctly on Cloud Run.
// Relying on HttpAgent's own `fetch` override instead left the token off the
// request in a production build, and the engine answered 401 UNAUTHENTICATED.
//
// The upstream body is passed straight through so SSE keeps streaming; this
// must not buffer, or the chat stops being incremental.
export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const upstream = await backendFetch("/api/adk", {
    method: "POST",
    headers: {
      "content-type": req.headers.get("content-type") ?? "application/json",
      accept: req.headers.get("accept") ?? "text/event-stream",
    },
    body: await req.text(),
    // @ts-expect-error -- Node's fetch needs this to stream a response body.
    duplex: "half",
  });
  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "content-type":
        upstream.headers.get("content-type") ?? "text/event-stream",
      "cache-control": "no-store",
      connection: "keep-alive",
    },
  });
}
