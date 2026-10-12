"use client";

// Keeps the CopilotKit thread id across reloads.
//
// The conversation itself lives server-side — in Agent Engine's managed
// sessions once the backend is deployed — but the browser holds the only
// pointer to it. CopilotKit mints a fresh thread id on every page load, so
// without this a reload (or anything that remounts the provider, like opening
// a post) silently starts a new conversation while the old one carries on
// existing, orphaned, on the server.
//
// Renders nothing; it exists for the effects. Must be inside <CopilotKit>,
// since useThreads() reads that provider's context.

import { useEffect, useRef } from "react";
import { useThreads } from "@copilotkit/react-core";

const STORAGE_KEY = "social-spark-thread";

// Start a fresh conversation: store a brand-new thread id and reload, so the
// restore effect below picks it up and the chat, pipeline and activity panels
// all start clean. The old conversation stays on the server (Sessions tab).
// Signing out deliberately doesn't do this; this is the explicit way.
export function startNewChat() {
  try {
    localStorage.setItem(STORAGE_KEY, crypto.randomUUID());
  } catch {
    /* storage disabled: reload still gives CopilotKit's own fresh thread */
  }
  window.location.reload();
}

export function ThreadPersistence() {
  const { threadId, setThreadId } = useThreads();
  const restored = useRef(false);

  // Restore once, on mount, before anything is sent.
  useEffect(() => {
    if (restored.current) return;
    restored.current = true;
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved && saved !== threadId) setThreadId(saved);
    } catch {
      /* private mode, or storage disabled — a fresh thread is a fine fallback */
    }
    // Deliberately mount-only: re-running this on every threadId change would
    // fight the save effect below and pin the thread to its first value.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Persist whatever the current thread is, including one we just restored.
  useEffect(() => {
    if (!threadId) return;
    try {
      localStorage.setItem(STORAGE_KEY, threadId);
    } catch {
      /* not being able to remember is survivable; crashing the app is not */
    }
  }, [threadId]);

  return null;
}
