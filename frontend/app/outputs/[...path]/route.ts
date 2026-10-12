import { backendFetch } from "@/app/lib/backend";

// Proxies generated images. backend/main.py mounts them at /outputs via
// StaticFiles; once the backend is deployed, the browser can't reach that
// directly (bearer token), so the image bytes come through here instead.
export const dynamic = "force-dynamic";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  // Rebuild the path segment-by-segment rather than trusting raw input, so a
  // crafted URL can't walk out of /outputs on the backend.
  const safe = path
    .filter((p) => p !== "." && p !== ".." && !p.includes("/"))
    .map(encodeURIComponent)
    .join("/");
  const upstream = await backendFetch(`/outputs/${safe}`);
  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "content-type":
        upstream.headers.get("content-type") ?? "application/octet-stream",
      "cache-control": upstream.ok ? "public, max-age=3600" : "no-store",
    },
  });
}
