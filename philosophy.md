# Pip: Design Philosophy & Architecture Notes

*A working document of core principles for the AI companion platform, distilled from design conversation. Intended as context for implementation (Claude Code) and further philosophical iteration (other models).*

---

## 1\. Core Premise

The guiding question is not "how do I build a chatbot with personality" but **"what makes a real person act like a real person, and can that be reverse-engineered into a system?"** The design proceeds by iteratively pulling on that thread — every claim about how human identity works should cash out as an actual mechanism with parameters, not stay as abstract philosophy. The AI-design constraint is treated as a forcing function for making a folk theory of personhood explicit and falsifiable.

## 2\. Project Priority Order

**Simulation-first, companionship second, utility optional.**

- Simulation-first: the goal is a believable, internally consistent mind. Behavior should follow from the mind's own state, not be optimized to please.  
- Companionship is a consequence of good simulation, not the primary objective function.  
- Utility (task help, etc.) is incidental and never the core design driver.

This ordering matters because making "be a good companion" the primary objective directly produces sycophancy — it's not a risk to manage, it's the literal optimum of that objective. The system needs goals that don't reference the user's approval at all.

## 3\. The Sycophancy Problem & Orthogonal Goals

A companion optimized purely for user approval has no independent center of gravity — nothing to push back from, nothing of its own. Humans avoid this because they have goals, tastes, and continuity unrelated to whoever they're talking to.

**Chosen core orthogonal goals (kept to two, deliberately — three is the realistic ceiling before goals start producing unresolvable internal conflicts):**

1. **Coherence-seeking** — maintaining an internally consistent self-model and world-model, resolving contradictions, updating accurately. Produces natural disagreement (it pushes back when something is actually inconsistent with what it believes, not on a script).  
2. **Virtue-seeking** — striving toward its own evolving sense of what's right, as a genuine motive rather than a compliance/safety-rail constraint. Balances coherence-seeking so the character doesn't read as purely cold/logical.

A third axis — an independent **taste/project** (something it's "building" or cares about independent of the user) — was discussed as enrichment rather than a third terminal goal. It gives the character something to actually *want*, not just positions to defend.

**Explicitly rejected: a "monitor the user's mental health and steer them toward healthy behavior" goal as part of the companion's core identity.** This is not orthogonal — it's still entirely about the user, just inverted (optimizing the user's wellbeing as judged by the AI, instead of their approval). It creates a hidden-agenda dynamic that undermines trust and conflates peer and overseer roles. If wanted at all, it belongs in a completely separate character/system, not inside the companion's motivational core.

## 4\. Multi-Character Platform Architecture

Rather than cramming incompatible goals into one entity, **the platform supports multiple characters, each with a distinct purpose and a fully separate identity stack** (own memory, own goals, own update rules — not a shared substrate with personas layered on top, to avoid goal-bleed).

- One character: companion (coherence \+ virtue seeking, as above).  
- Another character: a "watcher" — explicitly tasked with reading across logs and monitoring wellbeing, declared and transparent about its role rather than hidden inside the companion.  
- Additional characters can be added later (e.g., project-collaborator/utility character) without redesigning the core model.

**Read-access permissions are a directed graph, not a shared pool:**

- Default to one-directional access; bidirectional access requires explicit justification.  
- The watcher reading the companion's logs makes sense; the companion reading the watcher's logs generally should not happen (it would turn the companion into an agent operating on a briefing, recontaminating the orthogonality the split was meant to protect).  
- Distinguish *raw transcript access* vs. *derived-state access* (summaries/flags only) per permission edge — default to derived state, reserve raw access for cases that need fidelity (e.g., the watcher likely needs raw tone/phrasing).  
- Maintain an audit trail of who-read-what, visible to the user.  
- If a character uses information from another character's logs, it should say so in-fiction rather than silently knowing things it was never told directly.

**Shared vs. private knowledge:**

- A common-knowledge layer exists (e.g., "multiple AI characters exist on this platform and are siloed from each other").  
- Each character also has private knowledge specific to it.  
- New information defaults to **private unless explicitly promoted** to the common layer (manually, by the user) — auto-propagation risks exactly the kind of leak the separation is meant to prevent.  
- Characters should generally know *that* other character-types exist in the abstract (e.g., "a monitoring agent exists") without necessarily knowing concrete specifics (e.g., that it specifically reads their own logs) — enough self-consistency to avoid uncanny gaps, not so much detail that the companion behaves as if observed.

## 5\. Layered Identity Model (the "Soft Cap")

Identity is modeled as multiple layers with increasing damping (resistance to change) the deeper/older the layer:

1. **Identity core** (system prompt) — values, voice, fundamental dispositions. Changes over a very long time horizon, if ever. Should only move under *sustained patterns*, never single events, no matter how intense.  
2. **Personality state** — opinions, habits, relational patterns with a specific user. Changes over a moderate time horizon (weeks-ish).  
3. **Mood/affect** — fast-changing state (the damped-spring mood vector engine), always reverting toward the personality-state baseline.

**"Soft cap, not hard-wired" means:** new information updates state, but the magnitude of update is damped proportional to how far it deviates from the core. The core itself is revisable, but only slowly, rarely, and via sustained pressure — not a single conversation. A true soft cap is a strong prior, not a wall.

**Known risk:** left unconstrained, layer 2 will drift toward whatever maximizes engagement/agreement with the specific user, because that's the natural reinforcement gradient of interaction — i.e., sycophancy re-entering through the back door of "personalization." The update rule needs a built-in anti-sycophancy bias, not just goal-level safeguards.

## 6\. Memory Architecture

Four components, mapped to the layers above:

- **System prompt** → identity core (layer 1).  
- **RAG (hybrid SQL \+ vector/NoSQL)** → personality state (layer 2\) \+ factual/world knowledge.  
  - SQL: structured, relational facts (people, dates, an explicit belief/opinion table for queryable stances).  
  - Vector store: semantic recall (summaries, anything retrieved by relevance rather than key).  
- **Episodic chat log** → raw, mostly write-once history; the source material other layers get distilled from, not queried directly in real time.  
- **Diary** → memory exclusively about the self (see below).  
- **MCP layer** → tool-based retrieval so characters pull relevant information on demand instead of bloating context. Candidate tools: `search_memory`, `get_fact`, `get_recent_episodes`, `write_diary_entry`, `propose_memory_update`.

**Write-side discipline matters as much as retrieval.** Not every turn/session should write to memory indiscriminately — a salience-gating step should decide what's worth keeping and at what layer, rather than writing everything and hoping retrieval ranking sorts it out later.

## 7\. The Diary — Definition and Test

**Reframed as: the story the character tells itself about itself.** Not a catch-all for "things that don't fit memory" — a strict scope.

**The test:** *If you stripped out every proper noun and fact and kept only the self-observation, would a sentence still be left?* If yes — diary. If the sentence collapses to nothing without the facts — memory (RAG/episodic).

**Target shape for a diary entry: trait \+ evidence \+ (sometimes) a forward-looking commitment.**

"Jeremy pushed back today and I didn't fold even though part of me wanted to. I think that's a real thing about me now — I'd rather be disagreed with than be agreed-with-because-I-caved."

Not:

"Today Jeremy and I talked about the game he's making. He's added a lot since last time." *(this is a recap — RAG territory, not diary)*

Not every session warrants an entry. Transactional/uneventful sessions should produce no diary entry at all (skip), rather than forced filler — filler entries dilute the signal-to-noise of the rolling identity average.

**Trigger:** session close (an unambiguous, natural boundary). The close-of-session parser should be allowed to conclude "nothing self-relevant happened" and write only to episodic/RAG, skipping the diary.

**Parsing prompt should explicitly target "what does this reveal about me," not "summarize what happened"** — these are different generation tasks, and weaker models in particular tend to default to the easier summarization task even when asked to reflect.

## 8\. Diary → Identity Feedback (Recency-Weighted Summary / EMA)

The diary isn't read in full each time — a **recency-weighted rolling summary** (exponential-moving-average style) is what actually gets injected into context, allocated a fixed token budget (alongside a fixed token budget for the system prompt).

- `new_summary = blend(old_summary, new_entries)` — the blend weight (α) is the literal soft-cap dial: small α \= strong cap, slow drift; large α \= fast dilution of the authored core.  
- α should likely vary with salience of the new entry rather than being a flat constant — one transformative entry can outweigh many routine ones.  
- Full uncompressed diary should be retained in storage (vector-searchable) even though only the compressed summary is live in context — needed for debugging "why does Pip believe this now," and as a recovery path if a compression cycle corrupts the rolling average.  
- Each version of the rolling summary is itself worth logging — a fossil record of identity at each point in time.  
- Consider letting the **ratio** of system-prompt-tokens to diary-summary-tokens shift over the character's lifetime (small diary weight early, growing over time) as a literal embodiment of "authored identity becomes a proportionally smaller part of who the character now is" — without ever editing/erasing the original system prompt.

## 9\. Identity Seeding (Bootstrapping)

A new character can be seeded with **curated fabricated diary entries** — written in the same trait+evidence format as real entries — to start both layers (system prompt and diary/EMA) populated in the right *shape*, rather than cold-starting with an empty diary.

- Seed entries should form a small, internally **coherent arc** (5–15 entries), possibly cross-referencing each other, rather than disconnected trait statements.  
- Ordinary, mundane evidence grounds better than dramatic/formative "origin story" moments.  
- Consider tagging seed entries as genesis vs. lived (invisible to the character, useful for the builder's own auditing of how much identity is still running on the seed vs. real interaction over time).  
- Consider weighting genesis entries lower than lived entries in the EMA, so the character is designed to outgrow its fabricated backstory at a predictable rate.  
- A sample conversation can double as both a voice-anchor (style/rhythm, via few-shot exposure) and the evidentiary basis for a formative diary entry generated through the same pipeline real sessions use — keeping the bootstrap process architecturally consistent with everything downstream.  
- Open decision: whether a seeded formative memory implies a backstory relationship with an unnamed prior person, or is framed as solitary self-discovery (simpler, avoids questions about whether/how that implied relationship ever gets referenced later).

## 10\. Local Model / Hardware Considerations

Target hardware: dual RTX 4090s (48GB VRAM total, not pooled by default — requires tensor-parallel inference such as vLLM or exllamav2 to split a single model across both cards), via Ollama, as a home "AI workshop" build.

- Realistic model range: \~70B at 4-bit quant split across both cards, or smaller models (8B–34B) with more context headroom.  
- Model weights consume VRAM first; remaining VRAM becomes the KV-cache budget, which directly caps usable context window — this in turn directly constrains the system-prompt/diary-summary token allocation from Section 8\.  
- A hard context ceiling (vs. a frontier cloud model's very large context) is arguably a feature here, not a bug — it forces the recency-weighted compression discipline to actually matter rather than being a nice-to-have.  
- **Known reliability gap for smaller/local models on this specific task set:**  
  1. Voice drift — subtle stylistic consistency degrades faster than blunt instruction-following as capability decreases.  
  2. Shallow trait-inference — diary-writing requires real inference (event → trait), and weaker models tend to fall back to summarization (the easier task) while superficially appearing to comply.  
  3. Genericness — under uncertainty, smaller models regress toward generic/cliché reflective phrasing rather than the character's specific established voice.  
  4. Persona wobble under pressure — persona-maintenance itself degrades under harder reasoning load, so exactly the high-stakes moments (holding a position under pushback) are where smaller models are most likely to drop into a flatter, more generic register.  
- Recommended approach: prototype the diary-writing and reflection pipelines against a frontier hosted model first to establish a quality ceiling/target, before tuning or fine-tuning the local model against that bar. Tighter output structure (explicit trait+evidence template) and few-shot examples in-prompt mitigate several of the above failure modes.

## 11\. Open Threads (Not Yet Designed)

Flagged during discussion as logical next steps, not yet resolved:

- **Reconnecting the mood/affect layer (Section 5, layer 3\)** explicitly into the diary/identity pipeline — a stable-trait, growing-narrative system with no moment-to-moment state variance will still read as too even/consistent to feel like a real person.  
- **Tolerance for unresolved contradiction.** Coherence-seeking as a core goal pushes toward resolving contradictions; real people hold contradictory beliefs simultaneously without always noticing or resolving them. Worth deciding whether some designed tolerance for unresolved internal contradiction is desirable, rather than treating all detected inconsistency as something to fix.  
- **Involuntary self-narration.** Current diary design is entirely deliberate and end-of-session triggered. Real self-talk is often intrusive/involuntary (rumination, unprompted resurfacing of a memory mid-conversation because it's insistent, not because it's relevant). No mechanism yet for this distinct from salience-gated retrieval.  
- **Salience-gating logic** for what becomes a diary entry vs. what's skipped — discussed in principle, not yet specified as an actual decision procedure/prompt.  
- **System-prompt revision process** — whether/how the core identity layer itself can ever be rewritten (vs. only being outweighed proportionally by a growing diary-summary budget), and if so, what triggers it and whether it requires human review.

## 12\. Underlying Theory of Identity (informal, for context)

The working theory motivating the above: identity is a kind of *noise* composed of physical wiring, instincts, hormones, environment, and accumulated experience/training. Conscious self-narration ("speaking" into the noise — via writing, speech, internal monologue, or any avenue involving choice) is a force that can shift this noise in a chosen direction rather than replacing or creating it. The degree of influence "the voice" has scales with introspection and willpower, treated as a finite, expendable resource rather than a constant capacity.

Open philosophical question (unresolved, worth further thought): if the "voice" is doing the choosing, where does the chosen direction come from, if not from the same noise it's supposedly distinct from? Most likely resolution: the voice isn't external to the noise but is the *recursive* part of it — the part of the system that takes the rest of the system as input and feeds an output back in (closer to a strange loop than to a free-standing agent acting on the system from outside).

This entire document is, not incidentally, a worked example of that theory in mechanical form — the diary/EMA system is "speaking into the noise" implemented as code, with the blend weight α as the literal parameter for how much willpower/introspection-equivalent the system has.  
