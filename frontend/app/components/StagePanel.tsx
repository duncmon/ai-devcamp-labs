"use client";

import { useCoAgent, useCopilotChatInternal } from "@copilotkit/react-core";

type AgentState = {
  pipeline_stage?: string;
};

// Image generation happens inside draft_agent (folded into Drafting);
// memory consultation happens ahead of research.
const STAGES: { key: string; icon: string; label: string }[] = [
  { key: "idea", icon: "💡", label: "Idea" },
  { key: "consulting_memory", icon: "🧠", label: "Consulting memory" },
  { key: "researching", icon: "🔍", label: "Researching" },
  { key: "drafting", icon: "✍️", label: "Drafting" },
  { key: "awaiting_approval", icon: "⏳", label: "Approval" },
  { key: "posted", icon: "🚀", label: "Posted" },
];

function getActiveTool(messages: any[]): string | null {
  const toolResults = new Set<string>();
  for (const msg of messages) {
    if (msg.role === "tool" && msg.toolCallId) {
      toolResults.add(msg.toolCallId);
    }
  }
  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i];
    if (msg.role === "assistant" && Array.isArray(msg.toolCalls)) {
      for (let j = msg.toolCalls.length - 1; j >= 0; j--) {
        const call = msg.toolCalls[j];
        if (call?.id && !toolResults.has(call.id)) {
          return call.function?.name ?? null;
        }
      }
    }
  }
  return null;
}

/** Horizontal stepper mirroring the backend's pipeline_stage shared state,
 * with real-time in-flight synchronization for active subagent dispatches. */
export function StagePanel() {
  const { state } = useCoAgent<AgentState>({ name: "social_poster" });
  const { messages } = useCopilotChatInternal();

  let current = state?.pipeline_stage ?? "idea";
  const activeTool = getActiveTool((messages as any[]) ?? []);

  if (activeTool === "draft_agent") {
    current = "drafting";
  } else if (activeTool === "research_agent") {
    current = "researching";
  } else if (activeTool === "memory_agent" || activeTool === "load_memory") {
    current = "consulting_memory";
  }

  const currentIdx = STAGES.findIndex((s) => s.key === current);

  return (
    <section className="card">
      <h2>Pipeline</h2>
      <ol className="stepper">
        {STAGES.map((stage, i) => {
          const status =
            i < currentIdx ? "done" : i === currentIdx ? "current" : "";
          return (
            <li key={stage.key} className={`step ${status}`}>
              <div className="dot">{i < currentIdx ? "✓" : stage.icon}</div>
              {stage.label}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
