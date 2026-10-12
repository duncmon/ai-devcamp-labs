import { backendFetch } from "@/app/lib/backend";

// Proxies the gallery's post list. PostGallery.tsx used to fetch the backend
// directly from the browser, which stops working the moment the backend is on
// Agent Runtime — the passthrough needs a bearer token. Going through the
// server keeps the browser same-origin and token-free.
export const dynamic = "force-dynamic";

export async function GET() {
  const upstream = await backendFetch("/api/posts");
  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "content-type":
        upstream.headers.get("content-type") ?? "application/json",
      "cache-control": "no-store",
    },
  });
}
