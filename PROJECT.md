# Project: Twelve-Factor Backend Binding, Walkthrough & CLI Educational Guide

## Architecture
The Social Spark platform connects a Next.js (React / CopilotKit / AG-UI) frontend to an Agent Development Kit (ADK) / Vertex AI Reasoning Engine backend.
This project implements deterministic Twelve-Factor binding (Principles 1, 2, 3), authored walkthrough documentation with authentic evidence, an in-depth standalone educational guide for shell script CLI flags, and comprehensive browser and automated verification.

Data Flow & Integration:
1. `run-frontend.sh` parses CLI flags (`--local` vs `--cloud`) via a pure-Bash state machine, extracts configuration from `deployment_metadata.json` if in `--cloud` mode, and exports `ADK_BACKEND_ORIGIN`.
2. `frontend/app/lib/backend.ts` resolves `ADK_BACKEND_ORIGIN` strictly deterministically without silent fallback polling.
3. `frontend/app/api/backend-status/route.ts` probes `/healthz` of the configured backend origin and returns `{ origin, isLocal, healthy }`.
4. `frontend/app/page.tsx` renders `<BackendStatusBadge />` in `<Header />` providing instant visual status (`● Local (:8000)`, `☁ Vertex AI (...)`, or `⚠ Unreachable`).
5. `frontend/app/api/adk/route.ts` proxies requests to the backend. On connection error or 404 (torn-down Reasoning Engine), it streams structured AG-UI SSE diagnostic events directly into the chat UI with actionable recovery guidance.
6. `docs/walkthrough/backend-binding.html` provides a dedicated, dark-themed architectural and procedural guide documenting the implementation, failures/obstacles, and authentic screenshot evidence.
7. `docs/walkthrough/shell-script-flags.html` provides an educational guide with vector SVG diagrams detailing Approaches 1, 2, and 3 for shell flag parsing.
8. `docs/walkthrough/index.html`, `lab-1.html`, and `learnings.html` are updated with verified cross-links.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| F1 | Fail-Closed Diagnostics (Principle 1) | Deterministic binding in `backend.ts`; structured AG-UI SSE stream diagnostic events on 404 / connection failure in `adk/route.ts`. | M1 | ORIGINAL_REQUEST §R1 |
| F2 | Visual Observability Badge (Principle 2) | Implement `frontend/app/api/backend-status/route.ts` and `<BackendStatusBadge />` in `frontend/app/page.tsx`'s `<Header />`. | M1 | ORIGINAL_REQUEST §R1 |
| F3 | Launch Profiles (Principle 3) | Update `run-frontend.sh` to accept `--local` (default) and `--cloud`, parse `deployment_metadata.json`, and export `ADK_BACKEND_ORIGIN`. | M1 | ORIGINAL_REQUEST §R1 |
| F4 | Walkthrough Subpage Architecture & Content | Create `docs/walkthrough/backend-binding.html` with architectural rationale, implementation breakdown, testing, obstacles, and screenshots. | M2 | ORIGINAL_REQUEST §R2 |
| F5 | Walkthrough Cross-Linking | Link `backend-binding.html` cleanly from `docs/walkthrough/lab-1.html` (Step 8), `index.html`, and `learnings.html`. | M2 | ORIGINAL_REQUEST §R2 |
| F6 | Shell Script Flags Educational Guide | Create `docs/walkthrough/shell-script-flags.html` detailing Approaches 1, 2, 3, error handling, POSIX vs GNU/BSD compatibility. | M3 | ORIGINAL_REQUEST §R3 |
| F7 | Shell Script Flags Vector Diagrams | Author responsive vector SVG diagrams (Shift Stack mechanism and parsing state machine) styled via CSS variables in `shell-script-flags.html`. | M3 | ORIGINAL_REQUEST §R3 |
| F8 | Script & Build Verification | Run `bash -n run-frontend.sh` and Next.js / TypeScript builds cleanly with zero errors. | M4 | ORIGINAL_REQUEST §R4 |
| F9 | API Backend-Status Endpoint Verification | Verify `GET /api/backend-status` produces `{ origin, isLocal, healthy }` under local and simulated conditions. | M4 | ORIGINAL_REQUEST §R4 |
| F10 | Browser Rendering & Diagram Validation | Validate visual rendering, typography, responsiveness, and link navigation across all authored HTML subpages via browser inspection. | M4 | ORIGINAL_REQUEST §R4 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Backend Binding Implementation (R1) | `frontend/app/lib/backend.ts`, `frontend/app/api/adk/route.ts`, `frontend/app/api/backend-status/route.ts`, `frontend/app/page.tsx`, `run-frontend.sh` | none | DONE |
| M2 | Walkthrough Implementation Subpage (R2) | `docs/walkthrough/backend-binding.html`, cross-links in `index.html`, `lab-1.html`, `learnings.html` | M1 | DONE |
| M3 | Educational Guide on Shell Script Flags (R3) | `docs/walkthrough/shell-script-flags.html`, vector SVG diagrams, links to/from `backend-binding.html` and `index.html` | none | DONE |
| M4 | End-to-End Verification & Browser Validation (R4) | Bash syntax, Next.js build, API status test, and browser subagent validation of docs | M1, M2, M3 | DONE |

## Interface Contracts
### `GET /api/backend-status`
- Response 200 OK JSON:
  ```json
  {
    "origin": "http://localhost:8000" | "https://...",
    "isLocal": boolean,
    "healthy": boolean
  }
  ```

### AG-UI Stream Protocol on Error (`/api/adk`)
- Response headers: `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `Connection: keep-alive`
- Event sequence:
  1. `data: {"type": "RUN_STARTED"}\n\n`
  2. `data: {"type": "TEXT_MESSAGE_START", "messageId": "msg-error-...", "role": "assistant"}\n\n`
  3. `data: {"type": "TEXT_MESSAGE_CONTENT", "messageId": "msg-error-...", "delta": "...markdown diagnostic message..."}\n\n`
  4. `data: {"type": "TEXT_MESSAGE_END", "messageId": "msg-error-..."}\n\n`
  5. `data: {"type": "RUN_FINISHED"}\n\n`

### CLI Flag Contract for `run-frontend.sh`
- Usage: `./run-frontend.sh [--local | --cloud | -h | --help]`
- Default: `--local` -> `export ADK_BACKEND_ORIGIN="http://localhost:8000"`
- `--cloud` -> parse `remote_agent_runtime_id` from `deployment_metadata.json`, compute Vertex AI origin or URL, export `ADK_BACKEND_ORIGIN`.

## Code Layout
- `frontend/app/lib/backend.ts` — Origin resolution and deterministic backend configuration
- `frontend/app/api/adk/route.ts` — CopilotKit proxy route with AG-UI SSE stream error formatting
- `frontend/app/api/backend-status/route.ts` — Observability route returning JSON reachability
- `frontend/app/page.tsx` — Main application page hosting `<BackendStatusBadge />` in `<Header />`
- `run-frontend.sh` — Pure Bash flag parser and launcher
- `docs/walkthrough/backend-binding.html` — Architectural walkthrough subpage
- `docs/walkthrough/shell-script-flags.html` — Standalone educational guide
- `docs/walkthrough/index.html` — Walkthrough hub with nav links and bento tiles
- `docs/walkthrough/lab-1.html` — Lab 1 documentation with Step 8 deep-dive callout
