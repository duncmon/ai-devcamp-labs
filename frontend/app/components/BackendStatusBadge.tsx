"use client";

import { useEffect, useState } from "react";

interface BackendStatus {
  origin: string;
  isLocal: boolean;
  healthy: boolean;
  status?: number;
  error?: string;
  loading: boolean;
}

export function BackendStatusBadge() {
  const [status, setStatus] = useState<BackendStatus>({
    origin: "",
    isLocal: true,
    healthy: false,
    loading: true,
  });

  const checkStatus = async () => {
    try {
      const res = await fetch("/api/backend-status", { cache: "no-store" });
      if (!res.ok) {
        setStatus((prev) => ({
          ...prev,
          healthy: false,
          loading: false,
          error: `HTTP ${res.status}`,
        }));
        return;
      }
      const data = await res.json();
      setStatus({
        origin: data.origin ?? "",
        isLocal: Boolean(data.isLocal),
        healthy: Boolean(data.healthy),
        status: data.status,
        error: data.error,
        loading: false,
      });
    } catch (err: any) {
      setStatus((prev) => ({
        ...prev,
        healthy: false,
        loading: false,
        error: err?.message ?? "Network error",
      }));
    }
  };

  useEffect(() => {
    let mounted = true;

    const runProbe = async () => {
      try {
        const res = await fetch("/api/backend-status", { cache: "no-store" });
        if (!mounted) return;
        if (!res.ok) {
          setStatus((prev) => ({
            ...prev,
            healthy: false,
            loading: false,
            error: `HTTP ${res.status}`,
          }));
          return;
        }
        const data = await res.json();
        if (!mounted) return;
        setStatus({
          origin: data.origin ?? "",
          isLocal: Boolean(data.isLocal),
          healthy: Boolean(data.healthy),
          status: data.status,
          error: data.error,
          loading: false,
        });
      } catch (err: any) {
        if (!mounted) return;
        setStatus((prev) => ({
          ...prev,
          healthy: false,
          loading: false,
          error: err?.message ?? "Network error",
        }));
      }
    };

    runProbe();
    const interval = setInterval(runProbe, 10000);

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  if (status.loading) {
    return (
      <div
        className="backend-badge badge-loading"
        title="Checking backend reachability..."
      >
        <span className="badge-dot dot-pulsing" /> Checking backend…
      </div>
    );
  }

  if (!status.healthy) {
    const errorDetail = status.error ? ` (${status.error})` : "";
    return (
      <div
        className="backend-badge badge-unreachable"
        title={`Unreachable target: ${status.origin || "unknown"}${errorDetail} — click to retry`}
        onClick={checkStatus}
        role="button"
        tabIndex={0}
      >
        <span className="badge-icon" aria-hidden="true">
          ⚠
        </span>{" "}
        Unreachable
      </div>
    );
  }

  if (status.isLocal) {
    let port = "8000";
    try {
      if (status.origin) {
        const parsedUrl = new URL(status.origin);
        if (parsedUrl.port) port = parsedUrl.port;
      }
    } catch {
      // Fallback to default port
    }

    return (
      <div
        className="backend-badge badge-local"
        title={`Connected to local backend: ${status.origin} — click to re-check`}
        onClick={checkStatus}
        role="button"
        tabIndex={0}
      >
        <span className="badge-dot dot-green" /> Local (:{port})
      </div>
    );
  }

  // Deployed Cloud / Vertex AI state
  let location = "cloud";
  let shortId = "";
  try {
    const locMatch = status.origin.match(/locations\/([^/]+)/);
    if (locMatch) location = locMatch[1];
    const engMatch = status.origin.match(/reasoningEngines\/([^/]+)/);
    if (engMatch) {
      shortId = engMatch[1].slice(0, 4) + "…";
    }
  } catch {
    // Keep defaults
  }

  const cloudLabel = shortId ? `${location}:${shortId}` : location;

  return (
    <div
      className="backend-badge badge-cloud"
      title={`Connected to Vertex AI Reasoning Engine: ${status.origin} — click to re-check`}
      onClick={checkStatus}
      role="button"
      tabIndex={0}
    >
      <span className="badge-icon" aria-hidden="true">
        ☁
      </span>{" "}
      Vertex AI ({cloudLabel})
    </div>
  );
}
