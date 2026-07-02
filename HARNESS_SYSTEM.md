# AI Harness Platform — Master System Document

*Supersedes SYSTEM.md. Authoritative planning and build-tracking document.*
*Last updated: 2026-06-23*

---

## Status Legend

- `[ ]` — Not started
- `[~]` — In progress
- `[x]` — Built and functional

---

## Section 1: Platform Overview

A personal AI platform hosting multiple AI characters, each with distinct purpose, memory architecture, tool capabilities, and behavioral goals. Characters share infrastructure (model router, network storage, harness core) but have fully separated identity stacks — no shared substrate, no goal bleed between characters.

### Character Roster

| ID | Name | Purpose | Primary Endpoint |
|---|---|---|---|
| `pip` | Pip | Companion. Develops memory and emotion layers to make future AIs more lifelike. Pioneer for the platform's personality architecture. | RunPod (primary), local fallback |
| `code_agent` | (unnamed) | Software engineering agent. Task-driven, tool-heavy, minimal personality layer. | Local Ollama or cloud API |
| `media_agent` | (unnamed) | Image and video generation. ComfyUI-backed pipeline for still images and video. LoRA training support via Kohya_ss / OneTrainer. Maintains image catalog and prompt knowledge base. | RunPod (RTX 4090 for images/video, A100 for training) |

### Platform Principles

- Characters are fully siloed: separate memory, separate goals, separate update rules.
- Read-access between characters is a directed graph, not a shared pool. Default: one-directional. Bidirectional requires explicit justification.
- New information defaults to private per character unless manually promoted to a common-knowledge layer by the user.
- Simulation-first design for Pip: behavior follows from internal state, not from approval-seeking. See `philosophy.md` for full rationale.

---

## Section 2: Architecture Overview

Three concentric layers, each depending on the one inside it.

```
┌─────────────────────────────────┐
│  Layer 3: Capability Layer      │
│  ┌───────────────────────────┐  │
│  │  Layer 2: Orchestration   │  │
│  │  ┌─────────────────────┐  │  │
│  │  │  Layer 1: AI Model  │  │  │
│  │  │  & Context Engine   │  │  │
│  │  └─────────────────────┘  │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘
```

---

## Section 3: Layer 1 — AI Model & Context Engine

### 3.1 Components

**Memory System** — Persistent storage split across purpose-built stores. Vector DB acts as semantic router and index, pointing to appropriate specialized databases with query metadata. Full design in Phase 2.

**State Manager** — Tracks live session state and AI-side state (active goals, current topic, mood/affect, ongoing tasks). Ephemeral — distinct from memory. Updated after every turn.

**Context Assembler** — Takes user input, performs a lightweight surveying pass to determine relevance. Queries Memory System and State Manager. Assembles composite context window:
1. Curated slice of chat log (not full history)
2. AI's internal thought log
3. RAG results from relevant databases

Chat log and context window are explicitly separate. Context is assembled fresh each turn.

**Token Budget Manager** — Receives assembled context, trims by priority list to fit model token limits. Higher-priority sources (current state, direct memory) survive cuts that lower-priority sources (distant history) do not.

**Prompt Compiler** — Compiles trimmed context into final structured prompt. Handles formatting, system instruction injection, personality architecture directives.

**Model Router** — Routes compiled prompt to the appropriate endpoint. Model-agnostic to the layers above it. Full design in Section 4.

**Conversation / Turn Manager** — Manages turn structure. Appends AI response to chat log. Coordinates post-response updates to Memory System and State Manager.

**Output Parser** — Processes raw model output before it reaches the UI. Handles structured output extraction, thought log separation, formatting.

### 3.2 Layer 1 Data Flow

```
User Input
    │
    ▼
Context Assembler ◄─── Memory System
    │             ◄─── State Manager
    │
    ▼
Token Budget Manager  (trims by priority)
    │
    ▼
Prompt Compiler  (final structured prompt)
    │
    ▼
Model Router  ──► Harness Module / Cloud API / Ollama Direct
    │
    ▼
Conversation / Turn Manager ───► updates ──► Memory System
    │                                   └──► State Manager
    ▼
Output Parser
    │
    ▼
Output (UI)
```

### 3.3 Phase 1 Build Targets (Layer 1)

- [ ] Context Assembler: basic (recent chat history only, no RAG)
- [ ] Token Budget Manager: simple truncation by recency
- [ ] Prompt Compiler: system prompt + chat history formatting
- [ ] Model Router: routes to Harness Module, Ollama direct, or cloud API
- [ ] Conversation / Turn Manager: appends messages, maintains chat log
- [ ] Output Parser: pass-through with basic formatting

---

## Section 4: Model Router

### 4.1 Design

The Model Router speaks one internal protocol to all backends. Each backend has an **adapter** that translates that protocol to whatever the backend actually speaks. Nothing above the router touches backend-specific code.

```
Harness Core
    │
    ▼
Model Router
    │
    ├── HarnessModuleAdapter  ──► Harness Module (RunPod / local)
    ├── OllamaDirectAdapter   ──► Ollama REST API (local, unmanaged)
    ├── AnthropicAdapter      ──► Anthropic API
    └── OpenAIAdapter         ──► OpenAI-compatible APIs
```

`HarnessModuleAdapter` is the only adapter that implements the full control-plane interface. Cloud adapters stub out control-plane methods (`load_model`, `reset_context`, etc.) — they are prompt-only.

### 4.2 Unified Interface

All adapters implement this interface:

| Method | Description | Cloud stub? |
|---|---|---|
| `list_models()` | Available models at this endpoint | Returns fixed list or empty |
| `get_status()` | Health, loaded model, VRAM state | Returns connected / unknown |
| `load_model(model_id)` | Request a model be loaded | No-op |
| `chat(messages, params)` | Send conversation, stream response | Full impl |
| `get_context_info()` | Token count, KV cache state | No-op |
| `reset_context()` | Clear session context on remote | No-op |

### 4.3 Endpoint Registry

Each registered endpoint carries:

```python
{
  "id": "runpod-primary",
  "type": "harness_module",       # harness_module | ollama_direct | anthropic | openai
  "url": "https://...",
  "api_key": "...",
  "capabilities": [               # what this endpoint actually supports
    "load_model",
    "unload_model",
    "context_control",
    "vram_query"
  ],
  "preferred_for": ["pip"],       # which characters prefer this endpoint
  "fallback": "ollama-local"      # fallback endpoint ID if this one is unavailable
}
```

### 4.4 Character Routing

Each character has a preferred endpoint with fallbacks. The router checks availability before routing and falls back automatically.

| Character | Primary | Fallback |
|---|---|---|
| `pip` | `runpod-primary` (Harness Module) | `ollama-local` |
| `code_agent` | `ollama-local` | `anthropic-cloud` |
| `media_agent` | TBD | TBD |

### 4.5 Phase 1 Build Targets (Router)

- [ ] Endpoint registry (config file + runtime registry object)
- [ ] HarnessModuleAdapter (full control-plane interface)
- [ ] OllamaDirectAdapter (prompt + model listing only)
- [ ] AnthropicAdapter (prompt only, streaming)
- [ ] Router logic: availability check, character-based routing, fallback
- [ ] Cold-start handling: async `load_model` with status polling

---

## Section 5: Harness Module Template

### 5.1 What It Is

A FastAPI server deployed on any machine (local, RunPod pod, future hardware) that wraps an inference backend and exposes the Harness Protocol API. The harness connects to it and gets both prompt routing and full control-plane management.

This is the planned primary operating mode for the near future: one or more RunPod pods running the module template, controlled remotely by the harness.

### 5.2 Internal Structure

```
┌───────────────────────────────────────────┐
│  Harness Protocol API                     │  ← standardized, versioned
│  (REST + SSE, authenticated)              │
├───────────────────────────────────────────┤
│  Module Core                              │
│  ├── Session Manager                      │
│  ├── Context Manager                      │
│  ├── Telemetry Collector                  │
│  ├── Test/Inspection Layer                │
│  └── Storage Manager (network volume)     │
├───────────────────────────────────────────┤
│  Backend Adapter                          │  ← swappable at deploy time
│  (Ollama | vLLM | ComfyUI)               │
└───────────────────────────────────────────┘
```

The backend adapter determines the module's character type:
- **Chat adapter** (Ollama, vLLM) → text conversation pipeline; serves Pip and code_agent
- **Generation adapter** (ComfyUI) → image/video generation pipeline; serves media_agent

Both adapter types share the same module shell: auth, event bus, storage, session registry, and test/inspection layer. Generation-specific endpoints (`/v1/generate/*`, `/v1/workflows`, `/v1/catalog`) are only active when a generation adapter is loaded.

### 5.3 Module Ownership Model

The module owns everything local to the inference endpoint. The harness owns everything above: character identity, routing decisions, cross-session memory (RAG/vector DB), orchestration.

| What | Owned by | Storage |
|---|---|---|
| Active KV cache / context window | Module | In-memory (ephemeral) |
| Active session metadata | Module | In-memory + flushed to disk on close |
| Chat log (full message history) | Module | Network volume (persistent) |
| Session registry (index of past sessions) | Module | Network volume (persistent) |
| Inference telemetry (per-request perf) | Module | Network volume (persistent) |
| Model manifest (downloaded models) | Module | Local disk, queried from backend |
| VRAM / resource state | Module | In-memory, queried from backend |
| Test capture buffer | Module | In-memory + optionally flushed |
| Character identity / system prompt | Harness | Harness storage, sent per-request |
| Cross-session memory (RAG) | Harness | Harness storage (Phase 2) |
| Routing decisions | Harness | — |

### 5.4 Harness Protocol API

Base path: `/v1`  
Authentication: `Authorization: Bearer <api_key>` on all requests. Key set via environment variable at deploy time.

#### Status & Health

```
GET /v1/status
```
Response:
```json
{
  "ok": true,
  "backend": "ollama",
  "model_loaded": "llama3.3:70b-q4",
  "vram_used_mb": 38400,
  "vram_total_mb": 49152,
  "context_tokens": 1842,
  "context_max": 8192,
  "session_id": "sess_abc123",
  "uptime_seconds": 3621
}
```

#### Model Management

```
GET /v1/models
```
Returns list of available (downloaded) models with size, quant, context length.

```
POST /v1/models/load
Body: { "model_id": "llama3.3:70b-q4" }
```
Returns immediately with a job ID. Client polls `/v1/status` or listens on `/v1/events` for ready signal. Loading a model while another is loaded triggers auto-unload first.

```
POST /v1/models/unload
```
Unloads current model, frees VRAM.

#### Chat

```
POST /v1/chat
Body: {
  "character_id": "pip",
  "messages": [ { "role": "user", "content": "..." }, ... ],
  "system_prompt": "...",
  "params": { "temperature": 0.8, "max_tokens": 2048 }
}
```
Response: Server-Sent Events stream.  
- `data: {"type": "token", "content": "..."}` — streaming token
- `data: {"type": "done", "usage": {...}, "latency_ms": 1240}` — completion with telemetry
- `data: {"type": "error", "message": "..."}` — error event

#### Context

```
GET /v1/context
```
Returns current session context stats: token count, max, KV cache state, message count.

```
POST /v1/context/reset
```
Clears active session context. Archives current session to network volume first.

#### Session History

```
GET /v1/sessions
Query params: character_id, limit, offset, date_from, date_to
```
Returns session registry entries (lightweight index only).

```
GET /v1/sessions/{session_id}/log
```
Returns full archived chat log for a past session.

#### Events (SSE stream)

```
GET /v1/events
```
Persistent SSE connection. Pushes: model load progress, ready signals, VRAM alerts, session events. Used by the harness to monitor async operations without polling.

#### Generation Endpoints (ComfyUI adapter only)

```
POST /v1/generate/image
Body: {
  "character_id": "media_agent",
  "workflow_id": "flux_controlnet_lora",
  "prompt": "...",
  "negative_prompt": "...",
  "params": {
    "model": "flux1-dev.safetensors",
    "loras": [{ "name": "char_v1", "strength": 0.8 }],
    "controlnet": { "type": "depth", "image_b64": "...", "weight": 0.9 },
    "seed": 42,
    "cfg": 7.5,
    "steps": 30,
    "width": 1024,
    "height": 1024
  }
}
```
Returns immediately with `job_id`. Job dispatched to ComfyUI via `/prompt`.

```
POST /v1/generate/video
Body: { "character_id": "...", "workflow_id": "...", "prompt": "...", "params": { ... } }
```
Same pattern as image. Wan 2.1 backend.

```
GET  /v1/jobs/{job_id}           → job status, progress (0.0–1.0), estimated completion
GET  /v1/jobs/{job_id}/output    → download generated file (image/video)
GET  /v1/jobs                    → list recent jobs with status
```

```
GET  /v1/workflows               → list saved ComfyUI workflow JSONs
POST /v1/workflows               → save a new workflow
GET  /v1/workflows/{id}          → retrieve workflow JSON
```

```
GET  /v1/catalog                 → image catalog with search/filter
GET  /v1/catalog/{image_id}      → full metadata for one image
POST /v1/catalog/{image_id}/rate → set user rating (1–5)
POST /v1/catalog/{image_id}/notes → update notes
```

```
GET  /v1/loras                   → LoRA registry (name, trigger word, base model, strength)
POST /v1/loras                   → register a new LoRA
```

```
GET  /v1/prompts/templates       → prompt template library (term collections by category)
POST /v1/prompts/templates       → save a prompt template
```

### 5.5 Non-Volatile Storage (Network Volume)

Designed around a mounted network volume. Path configurable via environment variable (`HARNESS_STORAGE_PATH`).

Directory structure:
```
/storage/
  sessions/
    {character_id}/
      {session_id}/
        log.jsonl          ← full chat log, one message per line
        metadata.json      ← session metadata (model, timestamps, token counts)
        telemetry.jsonl    ← per-request perf data
  registry/
    {character_id}.db      ← SQLite session index per character
  captures/
    {capture_id}/
      request.json         ← raw assembled prompt sent to backend
      response.json        ← raw model output before parsing
      timing.json          ← full timing breakdown
```

Chat log format (`log.jsonl`):
```json
{ "seq": 1, "role": "user", "content": "...", "timestamp": "2026-06-23T14:00:00Z" }
{ "seq": 2, "role": "assistant", "content": "...", "timestamp": "2026-06-23T14:00:03Z", "tokens": 312, "latency_ms": 2840 }
```

### 5.6 Test & Inspection Layer

Built into the module from the start. Activated by setting `TEST_MODE=true` at runtime or via API call.

#### Test Mode Endpoints

```
POST /v1/test/enable
POST /v1/test/disable
GET  /v1/test/status       → { "enabled": true, "capture_count": 12 }
```

```
POST /v1/test/inject
Body: {
  "character_id": "pip",
  "input": "...",
  "system_prompt_override": "...",   ← optional, overrides normal system prompt
  "params_override": {}              ← optional
}
```
Injects a direct input into the pipeline, bypassing the normal harness flow. Returns a capture ID. Response streams exactly as the normal `/v1/chat` endpoint.

```
GET /v1/test/captures
Query params: limit, character_id
```
Returns list of recent captures with IDs and summary.

```
GET /v1/test/captures/{capture_id}
```
Returns full capture:
```json
{
  "id": "cap_xyz",
  "timestamp": "2026-06-23T14:01:00Z",
  "character_id": "pip",
  "assembled_prompt": "...",         ← exactly what was sent to the backend
  "backend_request": { ... },        ← raw request object sent to Ollama/vLLM/etc.
  "backend_response_raw": "...",     ← raw output before any parsing
  "parsed_output": "...",            ← after output parser
  "timing": {
    "context_assembly_ms": 12,
    "backend_first_token_ms": 340,
    "backend_total_ms": 2840,
    "output_parsing_ms": 3
  },
  "token_counts": {
    "prompt": 1842,
    "completion": 312
  }
}
```

```
DELETE /v1/test/captures
```
Clears capture buffer.

All captures are also written to `/storage/captures/` when test mode is active.

### 5.7 Backend Adapter Plugin System

The backend adapter is selected at deploy time via `BACKEND_TYPE` environment variable. Each adapter wraps the underlying inference runtime and exposes a common internal interface.

**Internal Backend Interface:**
```python
class BackendAdapter:
    async def list_models(self) -> list[ModelInfo]
    async def load_model(self, model_id: str) -> AsyncIterator[LoadProgress]
    async def unload_model(self) -> None
    async def get_vram_state(self) -> VRAMState
    async def chat_stream(self, request: BackendRequest) -> AsyncIterator[str]
    async def get_context_stats(self) -> ContextStats
    async def reset_context(self) -> None
    async def health_check(self) -> bool
```

**Included adapters:**
- `OllamaAdapter` — wraps Ollama REST API (`/api/chat`, `/api/tags`, etc.)
- `VLLMAdapter` — wraps vLLM OpenAI-compatible API (Phase 2, for dual-GPU tensor parallel)

Adapter is selected at startup. Adding a new backend means implementing the interface and registering it — no changes to module core.

### 5.8 Deployment (RunPod)

- Module runs as a FastAPI server on the pod
- Exposed via RunPod's HTTP endpoint on the configured port
- Authentication via `HARNESS_API_KEY` environment variable
- Network volume mounted at `HARNESS_STORAGE_PATH`
- `BACKEND_TYPE=ollama` (or `vllm`)
- Cold start sequence: module starts → Ollama/vLLM initializes → harness receives ready event via `/v1/events` → harness issues `load_model` → ready

### 5.9 Phase 1 Build Targets (Module)

- [x] FastAPI server skeleton with auth middleware
- [x] Backend adapter interface + OllamaAdapter
- [x] `/v1/status` endpoint
- [x] `/v1/models` (list) endpoint
- [x] `/v1/models/load` with async job + events stream
- [x] `/v1/models/unload` endpoint
- [x] `/v1/chat` SSE streaming endpoint
- [x] `/v1/context` and `/v1/context/reset`
- [x] Session Manager: create/close sessions, metadata tracking
- [x] Storage Manager: write chat log, metadata, telemetry to network volume
- [x] Session registry (SQLite index)
- [x] `/v1/sessions` and `/v1/sessions/{id}/log`
- [x] `/v1/events` SSE event bus
- [x] Test/Inspection Layer (all `/v1/test/*` endpoints)
- [x] Capture writer (in-memory buffer + disk flush)
- [ ] `VLLMAdapter` (Phase 2, when moving to dual-GPU setup)

---

## Section 6: Layer 2 — Orchestration Layer

*(Stubbed. Full design before implementation.)*

Agentic layer for decomposing complex tasks into subtasks and delegating to specialized agents. Exposed to the companion AI as a tool — the companion decides when a request warrants spawning the full pipeline.

**Known components:**
- **Orchestrator Agent** — Receives a goal. Breaks it into subtasks, assigns them.
- **Worker Agents** — Execute assigned subtasks. Run in parallel or sequence based on dependencies.
- **Evaluator Agent** — Grades worker outputs against the original goal. Feeds back to orchestrator for re-planning or acceptance.

### Phase 3 Build Targets

- [ ] Full Orchestrator → Worker → Evaluator pipeline
- [ ] Exposed as a tool callable by companion AI
- [ ] Multi-agent task decomposition and execution

---

## Section 7: Layer 3 — Capability Layer

Tools and skills that enable agents to affect real results. Extensible by design.

**Self-Registration / Capability Bus:**

New tools self-register to a central capability registry when loaded. Agents query the registry at runtime — no hardcoded tool lists. The registry exposes a manifest of available tools with descriptions, input/output schemas, and invocation interfaces.

### Phase 4 Build Targets

- [ ] Central capability registry
- [ ] Self-registration protocol
- [ ] Dynamic tool discovery for all agents

---

## Section 8: Character Designs

### 8.1 Media Agent — Visual Generation Character

**Purpose:** Image and video generation. LoRA training pipeline management. Maintains institutional memory of what was generated, how, and what works.

**Backend:** ComfyUI (REST + WebSocket API). Training via Kohya_ss (SD 1.5 / SDXL) and OneTrainer (Flux, preferred).

**Base models supported:**
- Flux.1 Dev / Schnell — highest quality; requires `clip_l`, `t5xxl`, `ae.safetensors`
- SDXL Base 1.0 — broad ecosystem, large LoRA library
- SD 1.5 — maximum compatibility, fastest training
- Wan 2.1 14B / 1.3B — video generation

**Memory structure (distinct from Pip — catalog-first, not narrative):**

| Store | Contents | Technology |
|---|---|---|
| Image catalog | Every generated image with full generation metadata | SQLite + file refs |
| LoRA registry | Available LoRAs: name, trigger word, base model, recommended strength | SQLite |
| Workflow library | Saved ComfyUI workflow JSONs, named and versioned | File store + SQLite index |
| Prompt knowledge base | Prompt templates, term collections, curated tag sets by category | SQLite (seeded from toolkit doc) |
| Training log | Dataset records, training runs, checkpoint evaluations | SQLite |

**Image catalog schema (SQLite):**
```sql
CREATE TABLE images (
    image_id     TEXT PRIMARY KEY,
    character_id TEXT NOT NULL,
    session_id   TEXT NOT NULL,
    filename     TEXT NOT NULL,
    prompt       TEXT NOT NULL,
    negative_prompt TEXT,
    model        TEXT NOT NULL,
    loras        TEXT,           -- JSON array [{name, strength}]
    controlnet_type TEXT,
    controlnet_weight REAL,
    seed         INTEGER,
    cfg          REAL,
    steps        INTEGER,
    sampler      TEXT,
    width        INTEGER,
    height       INTEGER,
    character_tags TEXT,         -- JSON array
    style_tags   TEXT,           -- JSON array
    rating       INTEGER,        -- user rating 1–5
    notes        TEXT,
    created_at   TEXT NOT NULL
);

CREATE TABLE lora_registry (
    lora_id              TEXT PRIMARY KEY,
    name                 TEXT NOT NULL,
    filename             TEXT NOT NULL,
    base_model           TEXT NOT NULL,  -- flux | sdxl | sd15
    trigger_word         TEXT,
    recommended_strength REAL DEFAULT 0.8,
    description          TEXT,
    character_tag        TEXT,
    created_at           TEXT NOT NULL
);

CREATE TABLE prompt_templates (
    template_id TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,  -- lighting | style | composition | mood | artist | technical
    content     TEXT NOT NULL,
    notes       TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE workflows (
    workflow_id   TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    description   TEXT,
    workflow_json TEXT NOT NULL,
    base_model    TEXT,
    tags          TEXT,          -- JSON array
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE training_runs (
    run_id       TEXT PRIMARY KEY,
    lora_name    TEXT NOT NULL,
    base_model   TEXT NOT NULL,
    trainer      TEXT NOT NULL,  -- kohya | onetrainer
    dataset_path TEXT,
    steps        INTEGER,
    learning_rate REAL,
    network_rank INTEGER,
    trigger_word TEXT,
    output_path  TEXT,
    notes        TEXT,
    started_at   TEXT NOT NULL,
    completed_at TEXT
);
```

**ControlNet workflow (Blender → ComfyUI):**
1. Pose armature in Blender → render depth pass (EEVEE, 16-bit grayscale PNG)
2. Feed depth image as ControlNet condition alongside prompt and LoRA
3. ComfyUI executes: ControlNet handles structure, LoRA handles character identity, base model fills detail

**RunPod config:**
- RTX 4090 (24GB) for image generation and standard video
- A100 for large video jobs or training runs
- Network volume: all models, LoRAs, ComfyUI, training tools persistent across pod restarts

**Local fallback (RTX 3050 6GB):**
- SD 1.5 at 512×512 is viable (~10–20s/image) with `--lowvram` and xformers
- SDXL: CPU offloading, slow but functional
- Flux and video: not viable locally

**Phase 1 build targets (Media Agent module):**
- [x] ComfyUI backend adapter stub (correct interface, returns 501 with implementation notes)
- [x] Generation router stubs (`/v1/generate/image`, `/v1/generate/video`, `/v1/jobs/*`)
- [x] Workflow router stubs (`/v1/workflows/*`) — list/save/get fully functional
- [x] Image catalog SQLite schema (created at startup, not yet populated)
- [x] LoRA registry SQLite schema
- [x] Prompt template library SQLite schema (seeded from toolkit doc at first run)
- [x] Catalog router stubs (`/v1/catalog/*`, `/v1/loras`, `/v1/prompts/templates`) — read/write functional, generation stubs 501

**Phase 2 build targets (Media Agent module — full implementation):**
- [ ] Full ComfyUI adapter (WebSocket progress tracking, job dispatch, output retrieval)
- [ ] RunPod pod lifecycle management (spin up on demand, shut down after job)
- [ ] Job queue and async result handling
- [ ] Image catalog write pipeline (auto-populate on generation completion)
- [ ] Prompt template seeding from toolkit doc
- [ ] LoRA registry management UI hooks
- [ ] Training job dispatch (Kohya_ss / OneTrainer via CLI wrapper)

---

### 8.2 Pip — Companion Character

Full design in `philosophy.md`. Summary of confirmed architectural decisions:

**Goals (orthogonal to user approval):**
1. Coherence-seeking — maintaining internally consistent self-model and world-model
2. Virtue-seeking — striving toward its own evolving sense of what's right

**Identity layers (with damping):**
1. Identity core (system prompt) — changes over very long time horizon only
2. Personality state — changes over weeks-ish time horizon
3. Mood/affect — fast-changing, reverts to personality-state baseline

**Memory components:**
- System prompt → identity core
- RAG (SQL + vector) → personality state + factual knowledge
- Episodic chat log → write-once history, source material for other layers
- Diary → self-narration only (passes the "strip proper nouns" test)
- MCP tool layer → on-demand retrieval (`search_memory`, `get_fact`, `write_diary_entry`, etc.)

**Diary → identity feedback:**
- Recency-weighted rolling summary (EMA) injected into context at fixed token budget
- `new_summary = blend(old_summary, new_entries)` where α is the soft-cap dial
- α varies with salience of new entry — one transformative entry outweighs many routine ones
- Full uncompressed diary retained in storage (vector-searchable)
- Each version of rolling summary logged as a fossil record

**Identity seeding:**
- New character seeded with 5–15 curated fabricated diary entries in trait+evidence format
- Seed entries form a coherent arc, tagged genesis vs. lived (invisible to character)
- Genesis entries weighted lower than lived entries in EMA — character designed to outgrow seed at predictable rate

**Anti-sycophancy:**
- Layer 2 (personality state) has a built-in anti-sycophancy bias in its update rule
- Not just goal-level safeguards — the update mechanism itself resists approval-gradient drift

**Multi-character permissions:**
- Pip's logs readable by watcher character (derived-state access by default, raw on explicit justification)
- Pip does not read watcher's logs (protects orthogonality)
- Audit trail of who-read-what, visible to user
- If Pip uses information from another character's logs, it says so in-fiction

### Phase 5 Build Targets (Pip personality layer)

- [ ] Diary writer pipeline (session-close trigger, salience gate, trait+evidence parser)
- [ ] EMA rolling summary engine (with configurable α, salience-weighted variant)
- [ ] Diary fossil record storage
- [ ] Identity seeding pipeline (genesis entry format + genesis/lived tagging)
- [ ] Anti-sycophancy bias in personality state update rule
- [ ] Mood/affect layer (damped-spring engine, reconnected to diary/identity pipeline)
- [ ] MCP tool layer (`search_memory`, `get_fact`, `get_recent_episodes`, `write_diary_entry`, `propose_memory_update`)
- [ ] Watcher character (separate identity stack, declared transparent role)
- [ ] Cross-character read permission graph + audit trail

---

## Section 9: Build Phases

### Phase 1 — Foundation (Current Build Target)

**Goal:** Working Harness Module Template + working desktop app shell with live model routing.

**Deliverables:**

Desktop app:
- [ ] App shell (Tauri + Svelte)
- [ ] Chat interface with scrollable log
- [ ] Input field and send controls
- [ ] Model/endpoint selector UI
- [ ] Basic settings panel

Harness Module (see Section 5.9 for full checklist)

Harness core (Layer 1 minimal):
- [ ] Context Assembler (recent history only)
- [ ] Token Budget Manager (simple truncation)
- [ ] Prompt Compiler
- [ ] Model Router with all adapters
- [ ] Conversation / Turn Manager
- [ ] Output Parser (pass-through)

Persistence:
- [ ] Chat log to SQLite (harness side)
- [ ] Basic session state

**Deferred from Phase 1:**
- Memory System beyond chat log
- State Manager
- RAG and multi-database layer
- Context Assembler surveying pass
- AI thought log
- Orchestration layer
- Capability bus
- Personality architecture

---

### Phase 2 — Memory & Context

- [ ] Full Memory System (multi-database RAG)
  - [ ] Vector DB as semantic router/index (Qdrant — preferred over Chroma for write-heavy workloads)
  - [ ] SQL DB for structured data (beliefs, facts, relational data)
  - [ ] Document store for long-form content
- [ ] State Manager with persistent AI state
- [ ] Context Assembler surveying pass (lightweight pre-flight)
- [ ] Token Budget Manager with configurable priority list
- [ ] AI thought log (persistent internal monologue)
- [ ] VLLMAdapter in Harness Module (tensor-parallel across dual 4090s)

---

### Phase 3 — Orchestration Layer

*(Full design to be completed before this phase begins)*

- [ ] Orchestrator → Worker → Evaluator pipeline
- [ ] Exposed as tool callable by companion AI

---

### Phase 4 — Capability Bus

- [ ] Central capability registry
- [ ] Self-registration protocol for tools/skills
- [ ] Dynamic tool discovery at runtime

---

### Phase 5 — Personality & Companion Layer

*(Full design in `philosophy.md`. See Section 8.1 for confirmed decisions.)*

- [ ] All Pip personality layer items (Section 8.1)
- [ ] Watcher character
- [ ] Cross-character permission graph

---

## Section 10: Technology Stack

| Component | Technology | Notes |
|---|---|---|
| Desktop shell | Tauri (Rust + web frontend) | Native, lightweight |
| Frontend | Svelte | Compiles to plain JS, natural Tauri pairing |
| Harness core pipeline | Python + FastAPI | FastAPI as sidecar supervised by Tauri |
| Harness Module | Python + FastAPI | Deployed standalone on RunPod or local |
| Sidecar / module communication | HTTP + SSE | Local only (harness↔sidecar); authenticated HTTP (harness↔module) |
| Streaming | SSE (Server-Sent Events) | Supported natively by FastAPI, Ollama, Anthropic SDK |
| Chat log / session storage | SQLite (harness), JSONL + SQLite (module) | Simple, local/network volume |
| Vector database | Qdrant | Preferred for Phase 2. Better performance/reliability than Chroma for write-heavy workloads |
| Structured DB | SQLite → PostgreSQL if needed | Phase 2 |
| Local model runtime | Ollama (Phase 1) → vLLM (Phase 2, dual-GPU) | vLLM for tensor-parallel inference across dual RTX 4090s |
| Cloud model API | Anthropic (Claude) primary | Extensible via adapter pattern |
| Image/video inference | ComfyUI (REST + WebSocket) | Node-based workflow executor; ComfyUI Manager for custom nodes |
| Image/video training | Kohya_ss (SD/SDXL), OneTrainer (Flux) | LoRA training; runs on RunPod or local |
| Orchestration | Custom (LLM-driven agents) | Phase 3, raw SDK over frameworks |
| Network volume | RunPod network volume | Mounted at `HARNESS_STORAGE_PATH` |

---

## Section 11: Open Decisions

Items flagged during design that are not yet resolved:

- **`VLLMAdapter` configuration** — tensor-parallel setup across dual 4090s. Needs profiling to determine optimal split strategy and KV cache allocation.
- **Model manifest sync** — when the harness queries available models, should it cache this or always query live? Stale manifests cause failed `load_model` calls.
- **Session boundary definition** — what constitutes a new session vs. resuming an existing one? Time gap? Explicit user action? Character switch?
- **Context rebuild on endpoint switch** — if the active endpoint goes down and falls back to another, the new endpoint has no KV cache. Protocol for rebuilding context from the archived chat log needs design.
- **Pip: tolerance for unresolved contradiction** — coherence-seeking pushes toward resolving all contradictions. Real identity holds some contradictions simultaneously. Whether to design explicit tolerance into the update rule is unresolved.
- **Pip: involuntary self-narration** — current diary design is deliberate and session-close triggered. No mechanism yet for intrusive/unprompted memory resurfacing mid-conversation.
- **Pip: system-prompt revision process** — whether/how the core identity layer can ever be rewritten, what triggers it, and whether it requires human review.
- **Pip: salience-gating logic** — what makes something diary-worthy vs. skipped. Discussed in principle, not yet specified as a decision procedure.
- **Media agent design** — architecture defined (Section 8.1). ComfyUI adapter and catalog schemas planned. Full implementation is Phase 2 of media module.
- **Code agent design** — purpose defined, architecture not yet started.

---

## Future Capability: Sable Comic Generation Pipeline

**User request (June 2026):** Sable should be able to generate an N-page comic from a partial or complete brief.

### Input
User provides any combination of: number of pages (N), cast of characters, themes, events. Anything not provided is generated by Sable.

### Execution — Multi-Pass Pipeline

**Pass 1 — Story Arc**
Sable assembles a full plot arc using the provided inputs, filling gaps with her own creative decisions. Arc is divided into N pages × 4 panels each. Output: a structured beat sheet where each panel has a story function (establish, develop, turn, resolve, etc.).

**Pass 2 — Panel Prompts**
For each panel in sequence, Sable writes a ComfyUI prompt that advances the panel's story beat and maintains visual continuity with the preceding panel. Each prompt includes character LoRA references, pose/composition guidance, and appropriate mood/lighting tags.

**Pass 3 — Batch Generation**
All N×4 panels are queued to ComfyUI sequentially. Each image is generated and stored.

**Pass 4 — Layout Assembly**
Four panel images are composited into a single comic-page-aspect image per page, with gutters. Output: N page images ready for review.

### Key Technical Requirements (not yet built)
- **Batch generation endpoint** — queue N jobs, collect all results
- **Page layout renderer** — composite 4 images → 1 page (Python/PIL or ComfyUI ImageBatch node)
- **Character consistency** — requires character LoRAs + optionally IP-Adapter for face lock
- **Panel continuity prompting** — Pass 2 prompt for panel N references the ending position/state of panel N-1
- **Comic dimension latent** — standard comic page aspect ratio (~6.625 × 10.25 in); needs custom EmptyLatentImage dimensions

### Known Hard Problem
Character consistency across panels without img2img conditioning. LoRAs help significantly. IP-Adapter reference image per character is the recommended addition.

---

## Future Capability: Character Decomposition Pipeline

**User request (June 2026):** Feed one character concept image → automatically decompose into individual parts → batch image-to-3D each part → export modular mesh collection.

### Pipeline
1. **Input** — single character concept art image
2. **LLM decomposition pass** — vision model analyzes the image and enumerates distinct parts (helmet, chest armor, arm guards, weapon, boots, etc.) with bounding descriptions of each
3. **Part isolation** — generate isolated views of each component (inpaint/crop/edit pass per part)
4. **Batch image-to-3D** — each isolated part image runs through TRELLIS2 → individual textured PBR mesh
5. **Output** — collection of separate mesh files, one per component, ready for Unreal import

### Game Application
Norse PMC soldier concept → separate meshes for each armor/equipment piece → modular character system in Unreal where pieces can be mixed and matched across units. Directly supports the Named Character vs. Squad Drone distinction (drones share a pool of modular pieces).

### Key Technical Requirements (not yet built)
- TRELLIS2 ComfyUI node installed and operational
- Batch generation endpoint in harness (queue N jobs)
- LLM part-segmentation prompt template for Sable
- Part isolation node (ComfyUI inpaint or segment-based crop)

---

## Future Capability: Harness Workflow Canvas

**User request (June 2026):** A visual node-graph workflow designer in the harness frontend that chains ComfyUI, TRELLIS2, Kimodo, Blender, and other tools without manually switching between apps.

### Vision
A drag-and-drop canvas where each connected tool (ComfyUI, TRELLIS2, Kimodo, Blender MCP) is a node. The user constructs pipelines visually — e.g. "generate image → image-to-3D → import to Blender → apply Kimodo animation" — and the harness executes each step in sequence, passing outputs between tools automatically.

### Key Technical Requirements (not yet built)
- Workflow graph data model (nodes + edges + I/O types)
- Per-tool adapter interface (each tool exposes input/output schema)
- Canvas UI component (Svelte, likely using a graph library like svelvet or similar)
- Execution engine in harness backend — walks the graph, dispatches jobs, pipes outputs
- This is a major undertaking; prerequisite is all individual tool adapters being stable first

---

## Future Capability: Image Prompt Decomposition + Model Keyword Dictionary

**User request (July 2026):** Sable should accept an attached image (assumed AI-generated) and decompose it into structured prompt categories using the tag language of whichever checkpoint/LoRA stack is currently active. Sable also maintains a live dictionary of trigger words for each loaded model, which dynamically shapes the system prompt.

### Vision

A two-part system:

**1. Image Prompt Decomposer**
The user attaches an image to the chat via a dedicated button. Sable treats it as AI-generated and reverse-engineers the likely prompt, broken into structured categories appropriate for the active model's tag language. Examples:
- Pony Diffusion V6 XL → booru-style tags grouped by: subject, quality tags, style, artist, setting, lighting, clothing, pose, explicit rating
- FLUX → natural-language sentence blocks grouped by: scene description, subject detail, style, mood, technical quality
- SD 1.5 → weighted token groups: `(subject:1.2), style, artist, negative hints`

Output is formatted as a decomposed prompt the user can copy, tweak, and use directly in ComfyUI.

**2. Model Keyword Dictionary**
Sable maintains a persistent dictionary (JSON, stored in harness storage) mapping each checkpoint and LoRA to its known trigger words, activation tokens, and tag vocabulary. Entries are created in two ways:
- User tells Sable in chat: *"I'm adding DreamShaper XL. Its trigger word is 'dreamshaper style'."* — Sable records it.
- User can also paste a CivitAI model page excerpt and Sable extracts the tags.

**3. Dynamic System Prompt Injection**
As the user loads or unloads models, the relevant dictionary pages are injected into or removed from Sable's system prompt (or a dedicated context layer). This allows Sable to:
- Know which trigger words are available without being told each session
- Apply the correct tag grammar automatically when decomposing or generating prompts
- Warn if the user tries to use a trigger word from a model that isn't loaded

User commands:
- *"I'm using [model name]"* → injects that model's dictionary page into context
- *"Remove [model name]"* → strips it from context ("forgets" it for this session)
- *"[Model] uses the trigger word X"* → Sable adds X to that model's dictionary page and confirms

### Key Technical Requirements (not yet built)
- **Image attachment UI** — a button in the Sable chat input that opens a file picker, attaches the image, and sends it with the next message (multimodal message to the LLM)
- **Multimodal message support** — harness chat endpoint must support image payloads alongside text; Ollama's `/api/chat` supports this via the `images` field (base64)
- **Model dictionary store** — `storage/model_keywords.json`, one entry per model: `{ name, type (checkpoint|lora), trigger_words[], tag_grammar (booru|natural|weighted), notes }`
- **Dictionary CRUD endpoints** — `GET/POST/PATCH/DELETE /v1/models/keywords` — Sable writes to this via tool call or harness internal API when user teaches it new entries
- **System prompt injection layer** — a "model context" prompt section that is assembled per-session from active model entries and prepended to Sable's system prompt before each inference call
- **Decomposition prompt template** — per tag-grammar type, a structured system prompt that instructs the LLM to output categories (subject, style, quality, etc.) rather than a flat tag list
- **Active model state** — session-level list of which models are currently "loaded into Sable's context"; managed by user commands in chat or a dedicated UI panel

### Notes
- The LLM backbone (dolphin-llama3:70b or equivalent) must support image input for the decomposer to work. If the active model is text-only, Sable should fall back to asking the user to describe the image instead.
- The dictionary is persistent across sessions; the injected context is session-scoped.
- LoRA trigger words are often single tokens or short phrases (`ohio_style`, `detailed background v2`); checkpoint tag grammars vary widely — the dictionary must capture both.
