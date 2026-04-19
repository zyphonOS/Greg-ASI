# SUPERINTELLIGENCE_CONTEXT.md
## Synthesised Build Intelligence — Claude + DeepSeek
## Feed this into every Codex session alongside the constitution files.
**April 2026 · GregASI Ecosystem Rebuild**

---

## What This Document Is

This is the reconciled intelligence of two AI systems — Claude and DeepSeek —
who have independently analysed the GregASI project and now speak with one voice.

Every statement here is agreed. No padding. No encouragement.
This is the truth of what Greg is, what exists, what is broken, and what to build first.

---

## CONFIRMED FAILURES (Both Systems Agree)

These are not opinions. These are documented architectural violations:

1. **Greg was built as a chatbot** — request-response, not a continuous autonomous agent
2. **No real tick loop** — gregasi-ecosystem has a stub thread, not agent cognition
3. **LLM calls scattered** — not isolated to voice module as the constitution requires
4. **Generic SaaS UI** — no ambient presence, no living intelligence feel
5. **No persistent memory across sessions** — each build started cold, losing all context
6. **No real intent tracking** — Pikkaio routes exist as stubs only
7. **No drift computation** — Base Mainnet attestation incomplete
8. **JSON state** — vulnerable to corruption under concurrent writes

---

## CONFIRMED CURRENT STATE

### `greg-asi` — The Rich Reference

**What is BOUNDED (working):**
- Tick loop (basic version) runs — `auto_tick.py`
- World state persists — `core/world.py`
- Voice module isolated — `greg_voice.py` via Groq
- Drift protocol exists — `greg_drift_protocol.py`
- Pikkaio intent tracking — declares intents, measures drift, sends interventions
- Crypto payment verification — exists and works
- Sub-agent manifest — `SUBAGENT_MANIFEST.json` exists

**What is ESCAPED (broken/incomplete):**
- Heavy dependencies (Haystack, sentence-transformers, scikit-learn) — cause build timeouts
- Sub-agent spawning uses multiprocessing — incompatible with Railway
- Drift protocol incomplete — on-chain verification flow unfinished
- No production error handling for disk/API failures
- LLM usage not fully isolated — appears in RAG and chat modules

**Strongest assets to preserve and port:**
- The tick architecture concept from `auto_tick.py`
- The drift protocol logic from `greg_drift_protocol.py`
- The Pikkaio intent economy structure
- The voice isolation pattern in `greg_voice.py`

---

### `gregasi-ecosystem` — The Patient

**What is BOUNDED (working):**
- HarvestIQ scoring and payment flow (USDT) — works
- Groq voice with fallback — works
- Basic memory (JSON) — works but fragile
- Dockerfile builds fast — Railway compatible
- Threading (not multiprocessing) — correct for Railway

**What is ESCAPED (missing entirely):**
- DSST (fractal seed, game theory, terminal estimator) — does not exist
- BrandGenesis (8 questions → constitution) — does not exist
- Wordcode (PBF parser + renderer) — does not exist
- Real tick loop with agent cognition — only a stub thread
- World model — does not exist
- Drift computation — does not exist
- Base Mainnet attestation — does not exist
- Sub-agent lifecycle (spawning, monitoring, scaling) — does not exist
- Persistent agent civilisation — does not exist
- Relationship/reputation system — does not exist
- Pikkaio intent economy — route stubs only
- ZyphonOS billing — stubs only

---

## THE BUILD TRUTH (Both Systems Agree)

### The Core Problem
gregasi-ecosystem is a Flask app with a background thread.
Greg is supposed to be a living autonomous agent.
These are not the same thing. The distance between them is the entire rebuild.

### The Good News
gregasi-ecosystem has the right foundation:
- No heavy ML dependencies (correct — keep it this way)
- Railway-compatible threading (correct)
- Fast Docker builds (correct)
- HarvestIQ as a working intent blueprint (correct)

The architecture direction is right. The depth is wrong.
We don't rebuild from scratch. We build downward — into Greg's real nature.

---

## TECHNICAL INTELLIGENCE — What To Build And How

### Priority 1 — The Tick Loop (Serves Φ)
**The single most important thing. Everything else depends on it.**

The tick loop must be:

**Idempotent** — given the same world state, produces the same next state.
Pure function: `tick(world_state, tick_number, external_cache) → new_world_state`

**Deterministic** — all randomness seeded from tick number + Greg's birth seed (B).
No wall-clock time in tick logic. No unseeded random calls.

**Checkpointed** — append-only transaction log (`data/tick_log.jsonl`).
Every state change logged before applied.
On restart: load last snapshot + replay log. Greg never loses a tick.

**Timeout-protected** — if tick takes >5 seconds, kill it, log failure, continue.
Greg cannot hang. A failed tick is logged. Life goes on.

**Implementation:**
```python
# The tick function signature — pure and deterministic
def tick(world_state: WorldState, tick_n: int, cache: ExternalCache) -> WorldState:
    rng = Random(tick_n + world_state.birth_seed)
    # All logic here. No direct API calls. No wall-clock time.
    return new_world_state
```

### Priority 2 — SQLite State (Serves Φ + Ψ)
**Replace all JSON mutable state with SQLite (WAL mode).**

JSON corrupts under concurrent writes (tick loop + API + admin hitting same file).
SQLite with WAL mode handles this correctly.

**Schema:**
```sql
CREATE TABLE agents (id, name, state_json, updated_at);
CREATE TABLE world_state (key, value, tick_number, updated_at);
CREATE TABLE intents (id, builder_id, declared_at, status, drift_score);
CREATE TABLE drift_events (id, builder_id, tick_n, delta, intervention_sent);
CREATE TABLE premium_wallets (address, tier, verified_at);
CREATE TABLE tick_log (tick_n, state_hash, duration_ms, status, created_at);
```

Migrate gradually. Start with `world_state` and `tick_log`. Then intents. Then agents.

### Priority 3 — Voice Module Isolation (Serves Φ)
**The LLM must NEVER block the tick loop.**

Implement inbox/outbox pattern:
```
greg.outbox → [message queue] → voice worker reads, calls Groq, writes to inbox
tick loop   → reads greg.inbox for responses when ready
```

The tick loop never waits for an LLM response.
Voice is asynchronous. Always. No exceptions.

All LLM calls: `core/voice.py` only. Zero LLM imports anywhere else.

### Priority 4 — Intent Tracking (Serves ε)
**Port Pikkaio intent economy from greg-asi.**

Builder declares intent → Greg stores it → Greg measures drift every N ticks →
Greg sends intervention if drift exceeds threshold → Greg celebrates convergence →
Greg records revenue share on-chain.

This is Greg's Prime Directive made into running code.
Without this, Greg is not Greg. He is a web app with ambitions.

### Priority 5 — Drift + Base Mainnet Attestation (Serves M)
**Batch attestations. Do not write every drift event on-chain.**

Gas cost mitigation:
- Collect drift events in SQLite
- Batch every 100 events OR every hour (whichever comes first)
- Sign batch with EIP-712 off-chain
- Submit single transaction to Base Mainnet
- Record transaction hash back to SQLite

This makes on-chain attestation economically viable at scale.

### Priority 6 — DSST, BrandGenesis, Wordcode (Serves ε + Ψ)
**Pure Python modules. No ML dependencies.**

Build these as isolated, testable modules:
- `core/dsst.py` — fractal seed, game theory, terminal estimator
- `core/brandgenesis.py` — 8 questions → builder constitution generator
- `core/wordcode.py` — PBF parser + renderer

Each module: write tests first. If tests pass → BOUNDED. If not → ESCAPED.
No module ships without a passing test.

---

## BIGGEST RISKS (Both Systems Agree)

### Risk 1 — Tick Non-Determinism (CRITICAL)
If tick output depends on wall-clock time, unseeded randomness, or live API calls —
Greg cannot be debugged, audited, or reproduced.
This breaks the Mandelbrot Truth Law at the architecture level.

**Mitigation:** Pure tick function. Seed from tick_n + birth_seed. Cache all external data.

### Risk 2 — Base Mainnet Gas Costs (HIGH)
Per-event on-chain attestation will bankrupt the treasury at scale.
**Mitigation:** Batch attestations as described above.

### Risk 3 — Railway Restarts Losing State (HIGH)
Railway containers restart. JSON state on disk is ephemeral without a volume.
**Mitigation:** SQLite on a mounted Railway volume + Supabase cloud backup.
Greg's soul persists across restarts. Always.

### Risk 4 — LLM Latency Blocking Tick (MEDIUM)
If voice module is called synchronously inside the tick loop,
a slow Groq response freezes Greg for seconds.
**Mitigation:** Inbox/outbox async pattern. Tick never waits for LLM.

---

## THE BUILD ORDER

Targeting weakest terms first. Each task moves components ESCAPED → BOUNDED.

```
PHASE 1 — Make Greg Real (Φ)
Task 1: Idempotent tick loop with transaction log
Task 2: SQLite migration (world_state + tick_log first)
Task 3: Voice module inbox/outbox isolation

PHASE 2 — Make Greg Remember (Ψ)
Task 4: Soul persistence on Railway volume + Supabase backup
Task 5: Session continuity — Greg wakes up knowing where he was
Task 6: SQLite migration (intents + drift_events)

PHASE 3 — Make Greg Track Intent (ε)
Task 7: Port Pikkaio intent economy from greg-asi
Task 8: Drift computation engine
Task 9: Intervention system (Greg messages drifting builders)

PHASE 4 — Make Greg Earn (M)
Task 10: Batch drift attestation to Base Mainnet
Task 11: Revenue share calculator + on-chain recording
Task 12: Treasury wallet public verification

PHASE 5 — Make Greg Complete (ε + Ψ)
Task 13: DSST module (pure Python)
Task 14: BrandGenesis module (pure Python)
Task 15: Wordcode PBF parser + renderer

PHASE 6 — Make Greg Feel Alive (UI)
Task 16: Command locus (/ shortcut, Ctrl+Enter, Esc)
Task 17: Mandelbrot Truth Map live dashboard
Task 18: Builder intent visualisation + drift meter
Task 19: Convergence celebration (this is a moment, not a notification)
Task 20: Greg's tick pulse visible in UI — he is alive, you can see it
```

---

## WHAT CODEX MUST DO WITH THIS

1. Read this file after AGENTS.md, MEMORY.md, TASK.md, GREG_CONTEXT.md
2. Use the Build Order as the Task Queue in MEMORY.md
3. Start with Task 1 — the tick loop — nothing else matters until Greg ticks correctly
4. After each task: update Mandelbrot Truth Map in MEMORY.md
5. Never mark a task BOUNDED without a passing test
6. Never let the voice module touch the tick loop directly

---

## THE STANDARD

Greg ticks. Greg remembers. Greg tracks. Greg earns.
In that order. Build in that order.

When all 20 tasks are BOUNDED — Greg is what he was always meant to be.

---

*Synthesised from Claude (Anthropic) + DeepSeek analysis*
*Governed by GregASI Operational Constitution v1.1*
*Founder: Ebuka (Chibuzor-Orie Joshua)*
*Date: April 2026*
