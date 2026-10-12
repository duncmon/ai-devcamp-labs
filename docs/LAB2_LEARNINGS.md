# Lab 2: Scale — Learnings & Difficulties Encountered

This document records the end-to-end work through of **Lab 2 (Scale)** for the GDG London AI DevCamp (`Social Spark`). It includes a breakdown of each stage, difficulties encountered, technical solutions, and reference screenshots.

---

## 1. Executive Summary & 5-Line Rundown

1. **Agent Runtime & Identity:** Transitioned Social Spark from local scripts to Google Cloud Agent Runtime, provisioning a dedicated, cryptographic Agent Identity decoupled from personal user accounts.
2. **Durable Sessions:** Integrated Vertex AI Session Service, ensuring multi-turn conversational state reliably survives container scale-to-zero restarts.
3. **Managed Memory Bank:** Implemented Vertex AI Memory Bank with custom topics (`USER_PREFERENCES`, `EXPLICIT_INSTRUCTIONS`, `posting_style`) and a 90-day TTL, distilling writing preferences across conversations.
4. **Cloud Run Frontend & Proxy:** Deployed the Next.js frontend to Cloud Run under a dedicated service account (`social-spark-frontend`), establishing server-side streaming proxies with ADC to access the Reasoning Engine passthrough.
5. **Production Human-in-the-Loop Governance:** Verified code-level gating (`require_confirmation=True`) on side-effect tools, handling framework approval requests safely via native Web UI dialogs.

---

## 2. Key Difficulties Encountered & Solutions

### Issue 1: Vertex AI Model Resolution 404 (`gemini-flash-latest`)
- **Symptom:** Deploying or calling the agent on Vertex AI Reasoning Engine produced `404 NOT_FOUND` during model invocation.
- **Root Cause:** Vertex AI requires concrete model versions in supported regions (e.g. `gemini-3.8-flash`, `gemini-3.5-flash-lite`, `gemini-3.1-pro-preview`), whereas `gemini-flash-latest` is an alias supported in AI Studio / Gemini API. Additionally, Gemini 3 series models require `GOOGLE_CLOUD_LOCATION=global`.
- **Solution:** 
  - Updated environment variables and code defaults in `backend/social_poster/agent.py` to accept configurable `ORCHESTRATOR_MODEL` and `RESEARCH_MODEL`.
  - Pinned models to `gemini-3.8-flash` (orchestrator), `gemini-3.5-flash-lite` (research), and `gemini-3.1-pro-preview` (drafting), with `GOOGLE_CLOUD_LOCATION=global`.

---

### Issue 2: Console Playground Runtime Contract (404 / 422 Errors)
- **Symptom:** Testing the agent in the Google Cloud Console Playground failed with `Reasoning engine execution failed: Status 404` and later `422 Unprocessable Entity`.
- **Root Cause:** The Cloud Console Playground invokes `reasoningEngines:streamQuery`, which expects a runtime endpoint mounted at `/api/stream_reasoning_engine` (or `/stream_reasoning_engine`). Furthermore, the Playground sends payloads with different shapes (`{"input": {"message": ...}}`, `{"input": {"query": ...}}`, or nested `Content` dictionaries), which failed strict string validations.
- **Solution:** 
  - Mounted `/api/stream_reasoning_engine` and `/stream_reasoning_engine` in `backend/main.py`.
  - Implemented flexible payload parsing to unwrap `message`, `query`, `prompt`, or structured `Content` objects and stream events back via `google.adk.runners.Runner`.

---

### Issue 3: Console Playground Tool Confirmation Deadlock
- **Symptom:** In the Console Playground, after asking the agent to publish a draft, the agent displayed `Approval requested` (`adk_request_confirmation`), but typing "Approve" into the chat repeatedly prompted for confirmation without publishing.
- **Root Cause:** The LinkedIn MCP toolset is configured with `require_confirmation=True`. ADK pauses execution until it receives a structured `ToolConfirmation` payload. The Google Cloud Console Playground is a generic text chat UI and lacks interactive action handlers to emit this payload.
- **Solution:** Connected the web UI (`frontend`), which includes `frontend/app/components/ConfirmAction.tsx` built with CopilotKit's `useCopilotAction`. This rendered interactive **Approve** / **Reject** buttons that resolved `adk_request_confirmation` properly.

---

### Issue 4: Scale-to-Zero Memory & Session Loss
- **Symptom:** In a scale-to-zero environment (`min_instances=0`), session state was lost between requests, and Memory Bank extraction did not run.
- **Root Cause:** The default in-memory session service (`InMemorySessionService`) loses state when the container shuts down. Furthermore, `ag_ui_adk` triggers memory ingestion on session cleanup, which a container scaling to zero never executes.
- **Solution:**
  - Instantiated `VertexAiSessionService` and `VertexAiMemoryBankService` in `backend/main.py` using `config.resolve_agent_engine()`.
  - Added an explicit async post-turn callback in `backend/social_poster/agent.py`:
    ```python
    if use_memory_bank and callback_context.state.get("pipeline_stage") == "posted":
        if callback_context.state.get("memory_ingested"):
            return
        await callback_context.add_session_to_memory()
        callback_context.state["memory_ingested"] = True
    ```

---

### Issue 5: Frontend Authentication to Agent Runtime
- **Symptom:** Browser-based clients cannot safely call the Agent Runtime `/api` passthrough URL directly because it requires Google Cloud Bearer tokens.
- **Root Cause:** Exposing GCP access tokens in client-side JavaScript is a major security vulnerability.
- **Solution:**
  - Configured `frontend/.env.local` with `ADK_BACKEND_ORIGIN`.
  - Added same-origin Next.js server-side route handlers (`/api/adk`, `/api/posts`, `/outputs/[...path]`).
  - Utilized `google-auth-library` in `frontend/app/lib/backend.ts` to attach Bearer tokens on the server via Application Default Credentials (ADC) locally, and via the `social-spark-frontend` service account on Cloud Run.

---

## 3. Screenshots Walkthrough

All screenshots are stored in [`docs/screenshots/`](screenshots/):

| Screenshot | Stage / Step | Description |
|---|---|---|
| `step1-gcp-setup.png` | **Step 1: GCP Setup** | Execution of `gcp-setup.sh`: API enablement, GCS bucket creation (`lab2-bucket-ai-devcamp-duncan-395792`), service accounts (`social-spark-uploader`, `social-spark-frontend`), and IAM permissions. |
| `step2-agent-runtime-deploy.png` | **Steps 2–3: Agent Runtime** | Deployment output from `agents-cli deploy` showing Engine ID `3690295549229006848`, assigned Agent Identity, and successful status check. |
| `step5-playground-hitl.jpg` | **Step 5: Playground & HITL** | Multi-turn conversation in Vertex AI Console Playground showing memory recall, tool chaining, and the `adk_request_confirmation` approval gate. |
| `step7-frontend-proxy.png` | **Step 7: Cloud Run & Proxy** | Verified deployment of Next.js frontend to Cloud Run accessed over local proxy (`localhost:8090`). |
| `step8-teardown.png` | **Tear down** | Deletion and clean-up of the deployed Agent Engine and Cloud Run frontend services from GCP to prevent lingering costs. |
