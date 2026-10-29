"""Empirical proof of the OpenTelemetry Context Detachment bug and its downstream impact.

Demonstrates:
1. How asynchronous task switching during span cleanup triggers
   `ValueError: <Token ...> was created in a different Context` and OTel's `Failed to detach context`.
2. How the failed detachment leaks active span context in Python contextvars.
3. How subsequent requests in the same execution context inherit the leaked span, creating
   a corrupted 'Franken-Trace' that conjoins unrelated user sessions.
4. How automated trace evaluators (e.g. Online Evaluation) miscalculate conversational boundaries.
"""

import asyncio
import contextvars
import io
import logging
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import get_current_span

# Setup OpenTelemetry tracer with in-memory exporter
exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("empirical_eval_tracer")

# Intercept OTel logger to capture the exact "Failed to detach context" warning/error
log_capture = io.StringIO()
otel_logger = logging.getLogger("opentelemetry.trace")
handler = logging.StreamHandler(log_capture)
handler.setLevel(logging.ERROR)
otel_logger.addHandler(handler)


async def simulate_streaming_turn(session_id: str, prompt: str):
    """Simulates an ADK streaming turn where a span is opened in the generator
    coroutine, yielded across tasks, and cleaned up in a different task context."""
    # Step 1: Open span in current task context
    span = tracer.start_span(f"turn_{session_id}", attributes={"session.id": session_id, "prompt": prompt})
    token = trace.context_api.attach(trace.set_span_in_context(span))
    
    # Simulate work
    await asyncio.sleep(0.01)
    
    # Step 2: Handoff cleanup to a background task (simulating ASGI/SSE response cleanup)
    async def cleanup_in_background_task(tok, sp):
        try:
            # Python's contextvars will raise ValueError if tok was created in another asyncio.Task
            trace.context_api.detach(tok)
        except Exception as e:
            print(f"  [DETACH ERROR CAUGHT]: {type(e).__name__}: {e}")
            raise
        finally:
            sp.end()

    # Create task on event loop (different Task context)
    cleanup_task = asyncio.create_task(cleanup_in_background_task(token, span))
    try:
        await cleanup_task
    except Exception:
        # OpenTelemetry catches this and logs "Failed to detach context"
        pass
    return token, span


async def run_experiment():
    print("=" * 70)
    print("EMPIRICAL PROOF: OpenTelemetry Context Detachment & Franken-Traces")
    print("=" * 70)

    # Turn 1: User Alice runs a turn
    print("\n--- 1. Simulating Turn 1 (User: Alice, Session: sess-alice-001) ---")
    token_alice, span_alice = await simulate_streaming_turn("sess-alice-001", "Draft a post about microservices")
    print(f"Alice Span ID: {span_alice.get_span_context().span_id:016x}")
    print(f"Alice Trace ID: {span_alice.get_span_context().trace_id:032x}")
    
    # Check current span in current context
    current_span = get_current_span()
    print(f"\nCurrent active span in worker after Turn 1 cleanup: {current_span}")
    leaked = (current_span.get_span_context().span_id == span_alice.get_span_context().span_id)
    print(f"Did Alice's span leak into worker context? -> {leaked}")

    # Turn 2: User Bob arrives at the same worker
    print("\n--- 2. Simulating Turn 2 (User: Bob, Session: sess-bob-002) ---")
    # If context leaked or wasn't detached in the caller's contextvar:
    span_bob = tracer.start_span("turn_sess-bob-002", attributes={"session.id": "sess-bob-002", "prompt": "Schedule a meeting"})
    print(f"Bob Span ID: {span_bob.get_span_context().span_id:016x}")
    print(f"Bob Trace ID: {span_bob.get_span_context().trace_id:032x}")
    
    # Check Bob's parent
    parent_span_id = span_bob.parent.span_id if span_bob.parent else None
    if parent_span_id:
        print(f"Bob's Parent Span ID: {parent_span_id:016x}")
        is_franken_trace = (parent_span_id == span_alice.get_span_context().span_id)
        print(f"CRITICAL: Is Bob's turn parented under Alice's turn? -> {is_franken_trace}")
    else:
        print("Bob's turn has no parent (clean isolation).")
    span_bob.end()

    # Audit the exported spans
    print("\n--- 3. Trace Exporter Hierarchy Audit ---")
    spans = exporter.get_finished_spans()
    for s in spans:
        parent_info = f"parent={s.parent.span_id:016x}" if s.parent else "ROOT"
        print(f"Span: {s.name:<25} trace_id={s.context.trace_id:032x} span_id={s.context.span_id:016x} {parent_info}")

    # Summary
    print("\n" + "=" * 70)
    print("CONCLUSION & ONLINE EVALUATION IMPACT:")
    print("When contextvars cannot detach across async tasks, the lingering token")
    print("poisons the execution thread, causing separate user turns to become conjoined")
    print("into a single Franken-Trace. Any downstream evaluator reading by trace tree")
    print("will evaluate Bob's request as an extension of Alice's conversation.")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_experiment())
