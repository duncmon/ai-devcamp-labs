"""AG-UI bridge: exposes the social_poster agent to the CopilotKit frontend.

Run from the repo root:  uv run uvicorn backend.main:app --port 8000
"""

import json
import logging
import os
import pathlib
import re

from ag_ui_adk import ADKAgent, add_adk_fastapi_endpoint
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from google.adk.memory import VertexAiMemoryBankService
from google.adk.sessions import VertexAiSessionService

log = logging.getLogger(__name__)

load_dotenv(pathlib.Path(__file__).parent / "social_poster" / ".env")

if os.environ.get("APP_URL"):
    os.environ.setdefault("GOOGLE_API_PREVENT_AGENT_TOKEN_SHARING_FOR_GCP_SERVICES", "false")

from backend.social_poster import db  # noqa: E402  (needs .env first)
from backend.social_poster.agent import root_agent  # noqa: E402  (needs .env first)

app = FastAPI(title="social-agent AG-UI backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_APP_URL_FULL_RE = re.compile(
    r"/projects/(?P<project>[^/]+)/locations/(?P<location>[^/]+)"
    r"/reasoningEngines/(?P<engine>\d+)"
)

app_url = os.environ.get("APP_URL", "").strip()
match = _APP_URL_FULL_RE.search(app_url) if app_url else None

if match:
    project = match.group("project")
    location = match.group("location")
    engine_id = match.group("engine")
    session_service = VertexAiSessionService(
        project=project,
        location=location,
        agent_engine_id=engine_id,
    )
    memory_service = VertexAiMemoryBankService(
        project=project,
        location=location,
        agent_engine_id=engine_id,
    )
    delete_idle_sessions = False
    log.info("Using VertexAiSessionService and VertexAiMemoryBankService on engine %s", engine_id)
else:
    session_service = None
    memory_service = None
    delete_idle_sessions = True
    log.info("Using in-memory session service")

adk_agent = ADKAgent(
    adk_agent=root_agent,
    app_name="social_poster",
    user_id="devcamp-user",  # single-user POC; extract from auth in real apps
    session_service=session_service,
    memory_service=memory_service,
    delete_session_on_cleanup=delete_idle_sessions,
)

add_adk_fastapi_endpoint(app, adk_agent, path="/api/adk")

# The console Playground and `reasoningEngines:streamQuery` call the runtime contract's
# native streaming route, which a container has to serve itself (the AG-UI route above is
# a different protocol). Request: {"class_method": "stream_query", "input": {"message",
# "user_id", "session_id"}}. Response: one JSON object per line, {"output": <ADK event>}.
# https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/runtime-contract
_native_runner = None


def _get_native_runner():
    global _native_runner
    if _native_runner is None:
        from google.adk.memory import InMemoryMemoryService
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService

        _native_runner = Runner(
            app_name="social_poster",
            agent=root_agent,
            session_service=session_service or InMemorySessionService(),
            memory_service=memory_service or InMemoryMemoryService(),
        )
    return _native_runner


@app.post("/api/stream_reasoning_engine")
@app.post("/stream_reasoning_engine")
async def stream_reasoning_engine(payload: dict):
    from fastapi.responses import JSONResponse, StreamingResponse
    from google.adk.agents.run_config import RunConfig, StreamingMode
    from google.genai import types

    log.info("stream_reasoning_engine incoming payload: %s", payload)
    args = payload.get("input") or {}
    raw_message = (
        args.get("message")
        or args.get("query")
        or args.get("prompt")
        or args.get("content")
        or payload.get("message")
        or payload.get("query")
        or payload.get("prompt")
    )
    if not raw_message:
        log.error("No message found in payload: %s", payload)
        return JSONResponse({"error": "input.message or input.query is required"}, status_code=400)

    if isinstance(raw_message, dict):
        try:
            content = types.Content.model_validate(raw_message)
        except Exception:
            text = raw_message.get("text") or str(raw_message)
            content = types.Content(role="user", parts=[types.Part(text=text)])
    elif isinstance(raw_message, str):
        content = types.Content(role="user", parts=[types.Part(text=raw_message)])
    else:
        content = types.Content(role="user", parts=[types.Part(text=str(raw_message))])

    runner = _get_native_runner()
    user_id = args.get("user_id") or payload.get("user_id") or "devcamp-user"
    session_id = args.get("session_id") or payload.get("session_id")
    session = None
    if session_id:
        try:
            session = await runner.session_service.get_session(
                app_name="social_poster", user_id=user_id, session_id=session_id
            )
        except Exception:
            session = None
    if session is None:
        session = await runner.session_service.create_session(app_name="social_poster", user_id=user_id)

    cfg = RunConfig(streaming_mode=StreamingMode.SSE)

    async def lines():
        try:
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session.id,
                run_config=cfg,
                new_message=content,
            ):
                yield json.dumps({"output": event.model_dump(mode="json", exclude_none=True)}) + "\n"
        except Exception as e:  # noqa: BLE001
            log.exception("stream_reasoning_engine failed")
            yield json.dumps({"error": str(e)[:300]}) + "\n"

    return StreamingResponse(lines(), media_type="application/x-ndjson")


# Serve generate_image's output files so the frontend's image gallery
# (PostGallery.tsx) can render them — tools.py writes local file paths, which
# the browser has no way to read directly otherwise.
GALLERY_DIR = pathlib.Path(__file__).resolve().parents[1] / "gallery"
GALLERY_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=GALLERY_DIR), name="outputs")


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/api/posts")
def posts() -> dict:
    """Published posts (with whatever image they used), read from the local
    SQLite store — durable across reloads/restarts, unlike ADK session state
    or the browser's own chat history."""
    return {"posts": db.list_posts()}
