import { NextResponse } from "next/server";
import { BACKEND_ORIGIN, backendFetch, needsGoogleAuth } from "@/app/lib/backend";

// Enforce dynamic execution on every request — do not cache probe responses
export const dynamic = "force-dynamic";

export async function GET() {
  const origin = BACKEND_ORIGIN;
  const isLocal = !needsGoogleAuth(origin);

  const noCacheHeaders = {
    "cache-control": "no-store, no-cache, must-revalidate",
    pragma: "no-cache",
  };

  try {
    // Probe backend using /openapi.json (universally supported on local FastAPI
    // and Cloud Vertex AI Agent Runtime reverse proxy, whereas /healthz is reserved/unrouted
    // on Agent Engine). Fall back defensively to /api/posts. Timeout set to 4000ms
    // to accommodate cold-starts on serverless runtimes.
    let probeRes = await backendFetch("/openapi.json", {
      signal: AbortSignal.timeout(4000),
    }).catch(() => null);

    if (!probeRes || !probeRes.ok) {
      probeRes = await backendFetch("/api/posts", {
        signal: AbortSignal.timeout(2000),
      }).catch(() => null);
    }

    if (probeRes && probeRes.ok) {
      return NextResponse.json(
        {
          origin,
          isLocal,
          healthy: true,
        },
        { headers: noCacheHeaders },
      );
    }

    return NextResponse.json(
      {
        origin,
        isLocal,
        healthy: false,
        status: probeRes ? probeRes.status : 503,
        error: probeRes ? `HTTP ${probeRes.status}` : "Endpoint unreachable",
      },
      { headers: noCacheHeaders },
    );
  } catch (err: any) {
    const errorMessage =
      err?.name === "TimeoutError"
        ? "Health check timed out (4000ms)"
        : err?.message ?? "Connection failed";

    return NextResponse.json(
      {
        origin,
        isLocal,
        healthy: false,
        error: errorMessage,
      },
      { headers: noCacheHeaders },
    );
  }
}
