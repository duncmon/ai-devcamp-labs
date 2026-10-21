"use client";

import { useEffect, useRef, useState } from "react";

interface BackendStatus {
  origin: string;
  isLocal: boolean;
  healthy: boolean;
  isBusy?: boolean;
  status?: number;
  error?: string;
  loading: boolean;
}

export function BackendStatusBadge() {
  const [status, setStatus] = useState<BackendStatus>({
    origin: "",
    isLocal: true,
    healthy: false,
    isBusy: false,
    loading: true,
  });

  const failureCountRef = useRef(0);

  const checkStatus = async () => {
    try {
      const res = await fetch("/api/backend-status", { cache: "no-store" });
      if (!res.ok) {
        failureCountRef.current += 1;
        if (failureCountRef.current >= 2) {
          setStatus((prev) => ({
            ...prev,
            healthy: false,
            isBusy: false,
            loading: false,
            error: `HTTP ${res.status}`,
          }));
        } else {
          setStatus((prev) => ({ ...prev, isBusy: true, loading: false }));
        }
        return;
      }
      const data = await res.json();
      if (data.healthy) {
        failureCountRef.current = 0;
        setStatus({
          origin: data.origin ?? "",
          isLocal: Boolean(data.isLocal),
          healthy: true,
          isBusy: false,
          status: data.status,
          error: undefined,
          loading: false,
        });
      } else {
        failureCountRef.current += 1;
        if (failureCountRef.current >= 2) {
          setStatus({
            origin: data.origin ?? "",
            isLocal: Boolean(data.isLocal),
            healthy: false,
            isBusy: false,
            status: data.status,
            error: data.error,
            loading: false,
          });
        } else {
          // 1st transient failure: retain healthy view, flag as busy
          setStatus((prev) => ({
            ...prev,
            origin: data.origin ?? prev.origin,
            isLocal: Boolean(data.isLocal),
            isBusy: true,
            loading: false,
          }));
        }
      }
    } catch (err: any) {
      failureCountRef.current += 1;
      if (failureCountRef.current >= 2) {
        setStatus((prev) => ({
          ...prev,
          healthy: false,
          isBusy: false,
          loading: false,
          error: err?.message ?? "Network error",
        }));
      } else {
        setStatus((prev) => ({ ...prev, isBusy: true, loading: false }));
      }
    }
  };

  useEffect(() => {
    let mounted = true;

    const runProbe = async () => {
      try {
        const res = await fetch("/api/backend-status", { cache: "no-store" });
        if (!mounted) return;
        if (!res.ok) {
          failureCountRef.current += 1;
          if (failureCountRef.current >= 2) {
            setStatus((prev) => ({
              ...prev,
              healthy: false,
              isBusy: false,
              loading: false,
              error: `HTTP ${res.status}`,
            }));
          } else {
            setStatus((prev) => ({ ...prev, isBusy: true, loading: false }));
          }
          return;
        }
        const data = await res.json();
        if (!mounted) return;
        if (data.healthy) {
          failureCountRef.current = 0;
          setStatus({
            origin: data.origin ?? "",
            isLocal: Boolean(data.isLocal),
            healthy: true,
            isBusy: false,
            status: data.status,
            error: undefined,
            loading: false,
          });
        } else {
          failureCountRef.current += 1;
          if (failureCountRef.current >= 2) {
            setStatus({
              origin: data.origin ?? "",
              isLocal: Boolean(data.isLocal),
              healthy: false,
              isBusy: false,
              status: data.status,
              error: data.error,
              loading: false,
            });
          } else {
            setStatus((prev) => ({
              ...prev,
              origin: data.origin ?? prev.origin,
              isLocal: Boolean(data.isLocal),
              isBusy: true,
              loading: false,
            }));
          }
        }
      } catch (err: any) {
        if (!mounted) return;
        failureCountRef.current += 1;
        if (failureCountRef.current >= 2) {
          setStatus((prev) => ({
            ...prev,
            healthy: false,
            isBusy: false,
            loading: false,
            error: err?.message ?? "Network error",
          }));
        } else {
          setStatus((prev) => ({ ...prev, isBusy: true, loading: false }));
        }
      }
    };

    runProbe();
    // 15-second polling interval balances observability with network overhead
    const interval = setInterval(runProbe, 15000);

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
        className={`backend-badge badge-local${status.isBusy ? " badge-busy" : ""}`}
        title={`Connected to local backend: ${status.origin}${status.isBusy ? " (busy processing...)" : ""} — click to re-check`}
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
      className={`backend-badge ${status.isBusy ? "badge-busy" : "badge-cloud"}`}
      title={`Connected to Vertex AI Reasoning Engine: ${status.origin}${status.isBusy ? " (active/busy...)" : ""} — click to re-check`}
      onClick={checkStatus}
      role="button"
      tabIndex={0}
    >
      <span className="badge-icon" aria-hidden="true">
        ☁
      </span>{" "}
      Vertex AI ({cloudLabel}{status.isBusy ? ":busy" : ""})
    </div>
  );
}
