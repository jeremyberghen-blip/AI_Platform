# MCP-Oriented AI Harness — System Document

---

## Section 1: What Is Currently Built

*Nothing built yet. This document tracks design and future implementation plans.*

---

## Section 2: Architecture Overview

The system is a personal AI harness built around three concentric layers, each depending on the one inside it.

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

### Layer 1 — AI Model & Context Engine

The core of the system. Responsible for constructing and curating everything that gets fed into the AI model, and routing that assembled context to the correct model.

**Components:**

- **Memory System** — Persistent storage split across multiple specialized databases. Different data types live in purpose-built stores (SQL for structured data, vector DB for semantic retrieval and routing, document store for long-form content, key-value for fast lookup). The vector DB acts as a semantic router and index — its entries point to the appropriate specialized database and include metadata about how to query it.

- **State Manager** — Tracks current session state and AI-side state (active goals, current topic, mood/tone context, ongoing tasks). Updated after every turn. Distinct from memory — state is live and ephemeral, memory is persistent.

- **Context Assembler** — Takes user input and performs a lightweight surveying pass to determine what information is relevant. Queries the Memory System and State Manager, then assembles a composite context window containing:
  1. A curated slice of the chat log (not the full history)
  2. The AI's internal thought log
  3. RAG results from relevant databases
  
  The chat log and context window are explicitly separate. The context window is assembled fresh each turn.

- **Token Budget Manager** — Receives the assembled context from the Context Assembler and trims it according to a priority list, ensuring the final prompt fits within model token limits. Higher-priority sources (e.g. current state, direct memory) survive cuts that lower-priority sources (e.g. distant chat history) do not.

- **Prompt Compiler** — Takes the trimmed context and compiles it into the final structured prompt to be sent to the model. Handles formatting, injection of system instructions, and personality architecture directives.

- **Model Router** — Routes the compiled prompt to the appropriate AI model based on current configuration. Supports switching between:
  - **Local:** Ollama-hosted models (runs on-device)
  - **Cloud:** External API models (e.g. Claude, GPT-4, Gemini)
  
  The router abstracts the model interface so the rest of the pipeline is model-agnostic.

- **AI Model** — The selected model that processes the prompt and generates a response.

- **Conversation / Turn Manager** — Manages turn structure, appends the AI response to the chat log, and coordinates post-response updates back to the Memory System and State Manager.

- **Output Parser** — Processes raw model output before it reaches the user. Handles structured output extraction, thought log separation, and formatting for the UI.

**Layer 1 Data Flow:**

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
Model Router  (local Ollama ─── or ─── cloud API)
    │
    ▼
AI Model
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

---

### Layer 2 — Orchestration Layer

*(Stubbed. Full design to be elaborated before implementation.)*

The agentic layer that enables the AI model to decompose complex tasks into simpler subtasks and delegate them to multiple specialized agents with distinct roles and instructions. Uses a multipass system to achieve long-horizon goals.

**Known components (to be fully designed):**

- **Orchestrator Agent** — Receives a goal or plan from the companion AI (Layer 1). Breaks it into subtasks and assigns them.
- **Worker Agents** — Execute assigned subtasks. May run in parallel or sequence depending on dependencies.
- **Evaluator Agent** — Grades worker outputs against the original goal. Feeds results back to the orchestrator for re-planning or acceptance.

The orchestration pipeline is exposed to the companion AI as a **tool** — the companion decides when a request warrants spawning the full pipeline rather than responding directly.

---

### Layer 3 — Capability Layer

Skills and tools that enable agents to affect real results. This layer is extensible by design.

**Self-Registration / Capability Bus:**

New tools and skills self-register to a central capability registry when they are loaded. Neither the companion AI nor the orchestrator has a hardcoded tool list — they query the registry at runtime to discover what is available. Adding a new capability means deploying it and letting it announce itself. The registry exposes a manifest of available tools with their descriptions, input/output schemas, and invocation interfaces.

---

## Section 3: Build Plan

### Phase 1 — Foundation (Current Build Target)

**Goal:** A working desktop application with a functioning chat interface and live model routing.

**Deliverables:**

- [ ] **Desktop app shell** (Tauri + web frontend)
  - Chat interface with scrollable chat log
  - Input field and send controls
  - Model selector UI (switch between Ollama / cloud)
  - Basic settings panel

- [ ] **Layer 1 core pipeline** (minimal viable)
  - Context Assembler: basic implementation (recent chat history only, no RAG yet)
  - Token Budget Manager: simple truncation by recency
  - Prompt Compiler: system prompt + chat history formatting
  - Model Router: routes to Ollama (local) or cloud API based on selection
  - Conversation / Turn Manager: appends messages, maintains chat log
  - Output Parser: pass-through with basic formatting

- [ ] **Persistence**
  - Chat log stored to disk (SQLite)
  - Basic session state (selected model, session ID)

- [ ] **Ollama integration**
  - Local model detection (query Ollama for available models)
  - Streaming response support

- [ ] **Cloud model integration**
  - At minimum: Claude (Anthropic API)
  - Streaming response support

**What is deliberately deferred from Phase 1:**
- Memory System (beyond chat log)
- State Manager
- RAG and multi-database layer
- Context Assembler surveying pass
- AI thought log
- Orchestration layer (stubbed interface only)
- Capability bus / tool registry
- Personality architecture

---

### Phase 2 — Memory & Context (Planned)

- Full Memory System with multi-database RAG
  - Vector DB as semantic router/index
  - SQL DB for structured data (e.g. game unit databases)
  - Document store for long-form content
- State Manager with persistent AI state
- Context Assembler surveying pass (lightweight pre-flight agent)
- Token Budget Manager with configurable priority list
- AI thought log (persistent internal monologue)

---

### Phase 3 — Orchestration Layer (Planned)

*(Detailed design to be completed before this phase begins)*

- Full Orchestrator → Worker → Evaluator pipeline
- Exposed as a tool callable by the companion AI
- Multi-agent task decomposition and execution

---

### Phase 4 — Capability Bus (Planned)

- Central capability registry
- Self-registration protocol for tools and skills
- Dynamic tool discovery at runtime for all agents

---

### Phase 5 — Personality & Companion Layer (Planned)

- Persistent personality architecture
- Long-term memory about the user
- Companion-layer identity and tone management

---

## Section 4: Technology Stack

| Component | Technology | Notes |
|---|---|---|
| Desktop shell | Tauri (Rust + web frontend) | Native desktop, lightweight |
| Frontend | Svelte | Lightweight, compiles to plain JS, natural Tauri pairing |
| Backend / core pipeline | Python + FastAPI | FastAPI runs as a sidecar process supervised by Tauri |
| Sidecar communication | HTTP / Server-Sent Events (SSE) | Local only, never leaves the machine |
| Streaming | SSE (Server-Sent Events) | Supported natively by FastAPI, Ollama, and Anthropic SDK |
| Chat log storage | SQLite | Simple, local, no server needed |
| Vector database | To be decided (Chroma, Qdrant, Weaviate) | Phase 2 |
| Structured DB | SQLite or PostgreSQL | Phase 2 |
| Local model runtime | Ollama | Local inference, streams by default |
| Cloud model API | Anthropic (Claude) | Primary cloud target; extensible to others |
| Orchestration | Custom (LLM-driven agents) | Phase 3, raw SDK preferred over frameworks |

---

*Last updated: 2026-06-08*
