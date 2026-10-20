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
    // Fast health probe with 2.5s timeout
    const probeRes = await backendFetch("/healthz", {
      signal: AbortSignal.timeout(2500),
    });

    if (probeRes.ok) {
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
        status: probeRes.status,
        error: `HTTP ${probeRes.status}`,
      },
      { headers: noCacheHeaders },
    );
  } catch (err: any) {
    const errorMessage =
      err?.name === "TimeoutError"
        ? "Health check timed out (2500ms)"
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
