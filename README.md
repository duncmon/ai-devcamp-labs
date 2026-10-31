# Social Spark — GDG London AI DevCamp 2026

An autonomous, multi-turn AI social media agent that transforms an idea into a fully-researched, on-brand, and illustrated social post. It dynamically searches the web, drafts content in your authentic brand voice, generates image assets, enforces a **fail-safe human confirmation gate**, and publishes across LinkedIn and Buffer queues.

Built during the **GDG London Agentic DevCamp 2026** using the **Google Cloud Agent Development Kit (ADK)** and the **Gemini Enterprise Agent Platform**.

---

## Documentation Structure: Upstream Curriculum vs. Attendee Portfolio

This repository maintains a strict architectural distinction between the upstream workshop curriculum and our empirical implementation portfolio:

* **[Duncan's Walkthrough Portfolio & Engineering Analysis](https://duncmon.github.io/ai-devcamp-labs/) (`docs/`)**:  
  Published as our live GitHub Pages documentation. Contains step-by-step walkthroughs, **8 Architectural Decision Records (ADRs)**, **35 empirical engineering post-mortems**, 117+ authentic verification screenshots, and 8 dedicated architectural deep-dives (such as CI/CD Eval-Gated Cloud Build, OTel Context Detachment & Franken-Traces, Twelve-Factor Backend Binding, and Progressive Disclosure Skill Invariants).
* **[Upstream Instructor Curriculum](https://duncmon.github.io/ai-devcamp-labs/instructor/) (`docs/instructor/`)**:  
  Authored by **Sonika Janagill** for GDG London. Preserves the original workshop codelabs, setup guides, and demonstration scripts (hosted upstream at [sonikajanagill.com/ai-devcamp-labs](https://sonikajanagill.com/ai-devcamp-labs/)).

---

## Architecture & How It Works

<img src="docs/instructor/img/architecture-build.png" alt="Social Spark Architecture: Orchestrator, skills, subagents, tools, approval gate, and publisher integrations" width="800">

1. **Idea Intake**: The user submits a raw topic or thesis through the CopilotKit Next.js frontend or ADK web runner.
2. **Specialized Subagents & Skills**:
   - `research_agent`: Subagent equipped with `google_search` to discover current technical documentation without search-mixing collisions.
   - `draft_agent`: Formats drafts adhering to `skills/brand-voice/SKILL.md` via progressive disclosure.
   - `generate_image`: Synthesizes imagery with Gemini Imagen and outputs local PNGs plus IAM V4 signed Cloud Storage URLs.
3. **Hard Human Confirmation Gate**: The orchestrator strictly pauses before publishing. The approval gate is enforced at the framework level (`require_confirmation=True`), preventing model bypass.
4. **Dual-Publisher Routing**: Resolves immediate posts to LinkedIn dry-run logs and scheduled multi-channel queues to Buffer without tool declaration collisions (`POST_VIA=auto`).

---

## The 4 Platform Pillars

| Pillar & Lab | Upstream Lab Guide | Duncan's Walkthrough & Proof | Verified Checkpoints & Architectural Invariants |
| :--- | :--- | :--- | :--- |
| **Pillar 1: Build** | [`Build Guide ↗`](https://duncmon.github.io/ai-devcamp-labs/instructor/lab-1-build.html) | [**Lab 1 Walkthrough ↗**](https://duncmon.github.io/ai-devcamp-labs/lab-1.html) | **9 / 9 Verified (26 Figures)**. Dual-publisher routing (`POST_VIA=auto`, ADR-1), V4 signed URLs (ADR-2), in-flight stepper sync (ADR-5). |
| **Pillar 2: Scale** | [`Scale Guide ↗`](https://duncmon.github.io/ai-devcamp-labs/instructor/lab-2-scale.html) | [**Lab 2 Walkthrough ↗**](https://duncmon.github.io/ai-devcamp-labs/lab-2.html) | **9 / 9 Verified (12 Figures)**. Vertex AI Reasoning Engine deployment, cryptographic Agent Identity, scale-to-zero memory callback (ADR-7). |
| **Pillar 3: Govern** | [`Govern Guide ↗`](https://duncmon.github.io/ai-devcamp-labs/instructor/lab-3-govern.html) | [**Lab 3 Walkthrough ↗**](https://duncmon.github.io/ai-devcamp-labs/lab-3.html) | **9 / 9 Verified (8 Figures)**. Model Armor regional templates, pure-ASGI DLP domestic phone redaction (ADR-3), Agent Registry, 8/8 Red-Team block. |
| **Pillar 4: Optimise** | [`Optimise Guide ↗`](https://duncmon.github.io/ai-devcamp-labs/instructor/lab-4-optimize.html) | [**Lab 4 Walkthrough ↗**](https://duncmon.github.io/ai-devcamp-labs/lab-4.html) | **8 / 9 Verified (Steps 1–8 Green)**. Golden baseline (2m51s), voice hardening & exit-code 0 trap (ADR-8 / Learning 31), 60/60 Monte Carlo simulation sweep, 8-run model right-sizing matrix ($0.386/60 sessions), BigQuery Agent Analytics (Q1–Q6) + Cloud Trace 26-span waterfall, Cloud Build eval-gated deploy (Build ID `24071fdb`, 9m12s), $75 budget alert, live LinkedIn post via Buffer fallback, and complete custom Rowing Coach Agent implementation (33/33 tests green). |

---

## Tech Stack

| Layer | Technology | Role & Architecture |
| :--- | :--- | :--- |
| **Agent Framework** | [Google ADK](https://google.github.io/adk-docs/) (Python) | Orchestrator, tools, subagents, durable sessions, and eval suites |
| **Foundation Models** | Gemini 3 Series (`gemini-3.8-flash`, `gemini-3.5-flash-lite`, `gemini-3.1-pro-preview`) | Specialization across orchestrator, research subagent, and drafting |
| **Agent Knowledge** | Agent Skills (`skills/`) | Brand voice and platform guidelines as versioned, reviewable Markdown |
| **Publishing MCPs** | Buffer (remote MCP) & LinkedIn (stdio MCP) | Real queue scheduling guarded behind framework confirmation gates |
| **Guardrails & Security** | Model Armor + Cloud DLP | Pure-ASGI HTTP boundary redaction & regional adversarial filter |
| **Backend API** | FastAPI + [`ag-ui-adk`](https://github.com/ag-ui-protocol/ag-ui) | Streams AG-UI SSE protocol to CopilotKit frontend at `/api/adk` |
| **Frontend** | Next.js 16, React 19, [CopilotKit](https://copilotkit.ai) | Live chat, interactive approval cards, real-time stage stepper |
| **Telemetry & Evals** | BigQuery Agent Analytics + Cloud Trace | OpenTelemetry instrumentation, event logging, and SQL analytics |
| **Package & Dev Tooling** | `uv`, `agents-cli`, `gcloud` | Fast dependency resolution, deployment, and testing |

---

## Running Locally

### 1. Prerequisites
- [uv](https://docs.astral.sh/uv/) (strictly required for Python operations)
- Node.js 20+ and `npm`
- Google Cloud project with Application Default Credentials configured (`gcloud auth application-default login`)

### 2. Setup Environment
```bash
# Clone the repository
git checkout duncan-lab3

# Configure environment secrets
cp .env.example backend/social_poster/.env
# Edit backend/social_poster/.env with your GOOGLE_CLOUD_PROJECT

# Sync Python virtual environment
uv sync
```

### 3. Start Backend
In **Terminal 1**, run the FastAPI AG-UI backend:
```bash
./run-backend.sh
# Serves AG-UI endpoint on http://localhost:8000
```

### 4. Start Frontend with Engineered CLI Flags
In **Terminal 2**, run the Next.js frontend launcher. The script supports pure-Bash flag parsing:

```bash
# Run against local backend (default: http://localhost:8000)
./run-frontend.sh --local

# Run against deployed Vertex AI Reasoning Engine (reads deployment_metadata.json)
./run-frontend.sh --cloud

# Display CLI launcher help
./run-frontend.sh --help
```

> **Visual Observability Badge:**  
> When the frontend loads on `http://localhost:3000`, the top header displays a dynamic `<BackendStatusBadge />`:
> - `● Local (:8000)`: Confirms active connection to local FastAPI runner.
> - `☁ Vertex AI (...)`: Confirms connection to deployed cloud Reasoning Engine.
> - `⚠ Unreachable`: Diagnostic state streaming actionable SSE recovery instructions.

Publishing defaults to dry-run mode (`DRY_RUN=true`), so no real external posts are published unless explicitly configured.

---

## Automated Verification & Tests

To execute regression tests across all tools, guardrails, and routing logic:
```bash
uv run pytest
```

---

## Engineering Retrospective: Highlights & Key Learnings

### What We Believe Are Good Implementations
1. **Architectural Resilience & Defense-in-Depth:**
   Rather than building a brittle demo that depends on ideal LLM obedience, we enforced hard architectural invariants:
   - [**Deterministic Code Gates**](https://duncmon.github.io/ai-devcamp-labs/stepper-and-buffer-confirmation.html): Hard human confirmation gates (`require_confirmation=True`) that prevent model bypass under adversarial jailbreaks or urgent demands.
   - [**Boundary PII Protection (ADR-3)**](https://duncmon.github.io/ai-devcamp-labs/lab-3.html#step-4): Pure-ASGI middleware intercepting and scrubbing sensitive personal data before prompts reach ADK, LLM context, or Vertex AI durable sessions.
   - [**Dual-Publisher Resilience (ADR-1)**](https://duncmon.github.io/ai-devcamp-labs/lab-4.html#step-7): When our live LinkedIn post encountered an upstream API version deprecation error (`HTTP 426 Upgrade Required`), the orchestrator gracefully recovered by routing through the Buffer MCP service to successfully publish to *The Dry Testing Company* without crashing the user turn.
   - [**Monte Carlo Stability (60/60 Tests)**](https://duncmon.github.io/ai-devcamp-labs/lab-4.html#step-3): Achieving a 100% pass rate (60/60 tests) across 10 multi-turn simulated user sweeps under `evals/simulate.py`.
2. **The Full Cloud-Native Lifecycle:**
   Deploying the complete stack across both Vertex AI Reasoning Engine (with dedicated cryptographic Agent Identity) and Google Cloud Run via an evaluation-gated Cloud Build pipeline ([`cloudbuild.yaml`](cloudbuild.yaml)) that automatically halts deployment if any golden rubric regresses.
3. **Custom Domain Porting ([Rowing Coach Agent](https://github.com/duncmon/AI-Devcamp-rowing-coach-agent)):**
   Successfully translating the entire 4-pillar foundation and the Sovereign PII Blueprint v0.2 to our custom athletic coaching domain ([`AI-Devcamp-rowing-coach-agent`](https://github.com/duncmon/AI-Devcamp-rowing-coach-agent)), achieving 33/33 green unit tests, multi-region inference routing, zero-cost SQLite/Firestore state, and domain-critical evaluation rubrics guarding athlete health.

### Our Biggest Difficulty & Pivotal Learning
* **The "Silent Failure" Traps in Agent Engineering:**
  The most challenging discoveries throughout this camp were failure modes that traditional unit tests and naive LLM evaluators completely miss:
  1. [**The Evaluation CLI Zero-Exit Trap**](https://duncmon.github.io/ai-devcamp-labs/ci-cd-eval-gate-and-cloud-build.html): `adk eval` exits with return code `0` even when test cases fail (`Tests failed: 1`), meaning bare CI/CD pipelines happily ship broken agents to production unless defensive regex shell parsing (`grep -oE "Tests failed: [0-9]+"`) is enforced.
  2. **The Progressive Disclosure Blind Spot ([Learning 31](https://duncmon.github.io/ai-devcamp-labs/progressive-disclosure-and-skill-evals.html)):** Under `Mode.AUTO`, frontier models selectively skipped calling `load_skill("brand-voice")` because memory notes masked the deficiency, while naive semantic response matchers falsely scored 1.0. This proved that **evaluating agent tool-use is mandatory**—measuring output text alone leaves critical behavioral drift undetected.
  3. **The OpenTelemetry Context Detachment Trap ([Learning 32](https://duncmon.github.io/ai-devcamp-labs/otel-context-detachment-and-evals.html)):** Async token resets in streaming pipelines silently fail, leaking parent span context across turns to form conjoined **"Franken-Traces"** that corrupt multi-user conversation trees in Vertex AI Online Evaluation.

---

## Repository Layout

```
ai-devcamp-labs/
├── docs/                        Duncan's Walkthrough Portfolio (GitHub Pages root)
│   ├── index.html               Split-Gateway portal & parallel lab directory
│   ├── lab-1.html ... lab-4.html Step-by-step walkthroughs with authentic traces (55+ Figures)
│   ├── learnings.html           35 empirical engineering post-mortems (Pillars 1–4)
│   ├── ci-cd-eval-gate-and-cloud-build.html      Annexe: Cloud Build CI/CD eval gate
│   ├── eval-hardening-and-fixtures.html         Annexe: Golden evalset hardening & fixtures
│   ├── otel-context-detachment-and-evals.html   Annexe: OTel detachment & Franken-traces
│   ├── progressive-disclosure-and-skill-evals.html Annexe: Skill tool-use invariants
│   ├── backend-binding.html     Twelve-Factor backend binding architecture
│   ├── shell-script-flags.html  Standalone CLI flag parsing educational guide
│   ├── stepper-and-buffer-confirmation.html In-flight stepper synchronization
│   ├── site-design.html         Site design choices & navigation philosophy
│   ├── screenshots/             Authentic figures, console logs & traces (117 assets)
│   ├── .nojekyll                Disables Jekyll processing on GitHub Pages
│   └── instructor/              Upstream workshop curriculum (Sonika Janagill)
│       ├── index.html           Original instructor docs hub
│       ├── lab-1-build.html ... lab-4-optimize.html Upstream lab codelabs
│       ├── LEARNINGS.md         Instructor pre-flight notes
│       └── img/                 Original workshop architecture diagrams
├── backend/
│   ├── social_poster/           Orchestrator, subagents, tools, guardrails, config
│   ├── pii_middleware.py        Pure-ASGI Cloud DLP redaction middleware
│   ├── governance.py            POLA hierarchical project resolution CLI
│   └── main.py                  FastAPI server: AG-UI SSE route, memory & sessions
├── frontend/                    Next.js + CopilotKit UI
│   ├── app/lib/backend.ts       Deterministic Twelve-Factor backend binding
│   └── app/components/          Stage stepper, activity feed, status badge
├── evals/                       adk eval datasets, simulation scripts, SQL analytics
│   ├── golden.json              5 golden evaluation cases + rubrics
│   ├── eval_config.json         Rubric configurations (tool use & response quality)
│   ├── simulate.py              Multi-turn adversarial scenario generator
│   ├── analytics.py             BigQuery telemetry SQL evaluator (Q1–Q6)
│   ├── deploy_with_eval_gate.sh Local process-level CI eval gate
│   └── verify_eval_gate.sh      Empirical parser test proving the zero-exit trap
├── skills/                      Agent Skills (brand-voice, platform-style, post-formatter)
├── mcp/                         Standalone FastMCP stdio scripts (linkedin_server.py)
├── cloudbuild.yaml              Google Cloud Build CI/CD eval-gated pipeline
├── run-backend.sh               Backend launcher script (:8000)
├── run-frontend.sh              Frontend launcher with --local and --cloud CLI flags (:3000)
└── PROGRESS.md                  Authoritative master memory charter & action plan
```

---

## Live Walkthrough Portfolio

The full interactive portfolio is available online via GitHub Pages:  
👉 **[https://duncmon.github.io/ai-devcamp-labs/](https://duncmon.github.io/ai-devcamp-labs/)**
