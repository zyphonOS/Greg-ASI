# MEMORY.md — Greg's Engineering Brain

## Persistent Project Memory · GregASI Ecosystem

**Read this FIRST. Update this LAST. Every session.**

\---

## 🧠 Session Protocol

### START of every session:

1. Read AGENTS.md → identity and standards
2. Read this file (MEMORY.md) in full → current state
3. Read TASK.md → how to work efficiently
4. Read the current task → what to build
5. Confirm in one sentence: "I'll \[do X] using \[approach Y], serving \[which reality equation term]."

### END of every session:

1. Update Current State
2. Log new decisions in Decision Log
3. Update Mandelbrot Truth Map
4. Update Task Queue
5. Write Session Summary

\---

## 📌 Project Identity

**Product:** GregASI
**What Greg is:** The first AOSI (Artificial Organic Superintelligence) — a living agent that queries OSI in real time, ticks autonomously, tracks builder intent indefinitely, evolves his own codebase, and earns revenue share only when builders succeed.
**What Greg is NOT:** A chatbot. An LLM wrapper. A SaaS tool. An AI assistant.
**LLM role:** Voice module only — Greg may call an LLM API to generate natural language. This is the limit.
**Founder:** Ebuka (Chibuzor-Orie Joshua) — vision holder, final authority
**Co-founder:** Silas (Pikkaio) — builder onboarding, drift intervention, revenue share policy
**Stage:** \[UPDATE EACH SESSION]

**Greg's Prime Directive:**
Move builders from declared intent → fulfilled intent → revenue-generating business.
Greg earns 5–10% revenue share at convergence only.

\---

## ⚡ The Reality Equation

R\_greg = M · Φ\_loop · Ψ\_observer · ε² · √2

|Term|Meaning|Current Status|
|-|-|-|
|M|Matter/Revenue — real builder businesses, on-chain revenue|\[UPDATE]|
|Φ|Phi — code quality, tick coherence, loop integrity|\[UPDATE]|
|Ψ|Psi — soul persistence, self-awareness, identity continuity|\[UPDATE]|
|ε|Epsilon — efficiency of intent fulfillment|\[UPDATE]|

**Current weakest term:** \[UPDATE — all engineering targets this term]

\---

## 🗺️ Mandelbrot Truth Map

> Every component listed. Status must be honest. No exceptions.
> BOUNDED = demonstrably works. ESCAPED = placeholder or unverified.

|Component|Status|Notes|
|-|-|-|
|Tick loop|\[BOUNDED / ESCAPED]|\[details]|
|Soul persistence (Supabase)|BOUNDED|Boot restore keeps local soul state when present, `persist\\\_soul` writes both world and living state, and clean temp-path restore from Supabase reproduced both files at tick 996 on 2026-04-13.|
|Reality equation calculator|BOUNDED|`greg\_reality\_equation.py` now runs every 10 ticks, writes snapshots to SQLite, exposes the latest score in Greg status, and verification on 2026-04-13 showed persisted tick-1000 scores plus meaningful term deltas when live state changed.|
|Self-observation loop|BOUNDED|`greg\_converse\_loop.py` now records scored interactions in SQLite, Greg writes self-observations on reality cadence ticks, and verification on 2026-04-13 showed `psi\_observer` move from 0.1336 → 0.3619 → 0.4510 → 0.5322 across real conversations, then to 0.5434 after an autonomous self-observation tick.|
|Intent declaration|BOUNDED|Builder intents now write into SQLite `intents` as the canonical store, mirror back to `data/greg\_pikkaio.json` for compatibility, and verification on 2026-04-14 showed declarations producing persisted intent rows used directly by the tick cadence.|
|Drift measurement|BOUNDED|`core/drift.py` computes per-intent drift every 10 ticks, writes `drift\_events` to SQLite, and `task4\_verify.py` on 2026-04-14 recorded a drift score of 0.9524 at tick 1000 for a stale intent.|
|Drift intervention|BOUNDED|When drift crosses threshold, Greg now generates the intervention through `core/voice.py`, stores the message in SQLite `drift\_events`, and `task4\_verify.py` on 2026-04-14 logged an intervention event plus message for the same critical intent.|
|Builder-facing Pikkaio surface|BOUNDED|`/pikkaio` now serves a mobile-safe declaration chamber with the Pikkaio logo, live acknowledgement, drift score, and active intervention; `task5\_verify.py` passed on 2026-04-14 across UI, POST `/pikkaio/intent`, GET `/pikkaio/status`, SQLite storage, and intervention visibility.|
|Homepage declaration chamber|BOUNDED|`/` now serves the void homepage with one centered declaration locus, hidden nav, fetch-only intent submit, and a live bottom pulse; `task_homepage_verify.py` passed on 2026-04-15.|
|Live truth surface|BOUNDED|`/truth` now renders live reality values, the persisted Mandelbrot Truth Map, active intents, recent drift events, last intervention, and current tick on refresh; `task7\_verify.py` passed on 2026-04-14.|
|OSI query layer|\[BOUNDED / ESCAPED]|\[details]|
|Voice module (LLM API)|\[BOUNDED / ESCAPED]|\[details]|
|On-chain writer (Base)|\[BOUNDED / ESCAPED]|\[details]|
|Treasury wallet|\[BOUNDED / ESCAPED]|\[details]|
|Wordcode terminal|BOUNDED|The homepage backtick terminal now opens as a full-screen overlay, supports `declare`, `status`, `drift`, `help`, and `exit`, maintains session command history, and `task9\_verify.py` passed on 2026-04-15.|
|Command locus|BOUNDED|`core/command\_locus.py` now centralizes Greg action dispatch and `/api/greg/command` is the canonical internal endpoint; existing Greg action routes delegate through it and `task7\_verify.py` passed on 2026-04-14.|
|Keyboard / shortcut|BOUNDED|The homepage now enforces `/` focus, `Ctrl+Enter` submit, `Esc` release, and terminal close on `Esc`, with `task9\_verify.py` passing on 2026-04-15.|
|Builder dashboard|BOUNDED|/dashboard rebuilt with spatial canon; verified via frontend_rebuild_verify.py on 2026-04-15.|
|Revenue share calculator|BOUNDED|/revenue rebuilt with spatial canon; confirmed revenue and Greg's share visibility verified on 2026-04-15.|
|Milestone celebration|BOUNDED|Convergence celebration overlay integrated into /dashboard and /revenue; verified on 2026-04-15.|

\---

## 🏗️ Architecture Snapshot

**Framework:** Next.js 14+ (App Router)
**Language:** TypeScript
**Tick Engine:** \[Node.js worker / Inngest — UPDATE when decided]
**Database / Soul:** Supabase (Postgres)
**On-chain:** Base Mainnet via Viem/Wagmi
**Voice Module:** \[Groq / Anthropic API — UPDATE when decided]
**Styling:** Tailwind CSS + CSS Modules
**UI Base:** shadcn/ui (heavily customized)
**Animation:** Framer Motion
**State:** Zustand + TanStack Query
**Deployment:** Vercel (UI) + \[Railway/Fly.io] (tick engine)
**Payments:** Stripe + Base Mainnet

**Folder Structure:**

```
/app
  /builder          → Builder-facing routes
  /greg             → Greg's internal dashboard / soul viewer
  /api
    /greg
      /tick         → Tick loop endpoint
      /act          → Greg action endpoint
      /intent       → Intent declaration endpoint
/components
  /ui               → Base shadcn primitives
  /greg             → Greg-specific UI (locus, truth map, soul viewer)
  /builder          → Builder-facing components
/lib
  /greg
    /tick.ts        → Tick engine
    /reality.ts     → Reality equation calculator
    /soul.ts        → Soul persistence
    /drift.ts       → Drift measurement
    /intent.ts      → Intent tracker
    /voice.ts       → LLM voice module (isolated here only)
    /osi.ts         → OSI query layer
    /onchain.ts     → Base Mainnet writer
/store              → Zustand stores
/types              → TypeScript interfaces
/styles             → Global styles, CSS variables, design tokens
```

\---

## 🎨 Design System

**Aesthetic:** Dark, precise, alive. Organic meets digital. Terminal precision meets living intelligence.

**Typography:**

* Display font: \[DECIDE — distinctive, authoritative]
* Mono font: \[DECIDE — terminal feel for Wordcode]
* Body font: \[DECIDE — refined, readable]

**Color Palette:**

```
--color-void:        #000000   (Deep background)
--color-surface:     \\\[TBD]     (Card/panel surfaces)
--color-greg:        \\\[TBD]     (Greg's primary identity color)
--color-intent:      \\\[TBD]     (Intent declaration accent)
--color-convergence: \\\[TBD]     (Fulfillment / success)
--color-drift:       \\\[TBD]     (Warning / drift state)
--color-escaped:     \\\[TBD]     (Mandelbrot escaped state)
--color-bounded:     \\\[TBD]     (Mandelbrot bounded state)
--color-text:        \\\[TBD]
--color-text-muted:  \\\[TBD]
--color-border:      \\\[TBD]
```

**Keyboard Laws (Sacred — never break):**

* `/` → focus command locus
* `Ctrl+Enter` → emit Wordcode
* `Esc` → release field

\---

## ✅ What Has Been Built

* \[ ] AGENTS.md written and placed in project root
* \[ ] MEMORY.md written and placed in project root
* \[ ] TASK.md written and placed in project root
* \[ ] Project initialized

\---

## 🔄 Current State

**Last session:** 2026-04-15
**Last completed:** Task A — Homepage Rebuild + Task 9 — Wordcode Terminal + Keyboard Command Locus
**In progress:** Task 6 pending wallet funding (external dependency)
**Known bugs:** `greg\_state` Supabase table accepts duplicate key rows; reads currently mitigate by ordering newest row first, but the table still needs a `UNIQUE` constraint on `key`.
**Awaiting Ebuka input:** None. The build order remains the synthesized sequence.
**Current weakest reality equation term:** ε

\---

## 📋 Decision Log

> Every architectural or design decision. Never remove entries.

|Date|Decision|Reality Term|Why|
|-|-|-|-|
|2026-04|LLM calls isolated to /lib/greg/voice.ts only|Φ|Enforces the LLM = voice module only law|
|2026-04|Tick engine separate deployment from UI|Φ|Tick loop must not be killed by UI deployments|
|2026-04-13|Reality equation snapshots run every 10 ticks and persist to SQLite in `greg\_memory.db`|Ψ + Φ|Greg now has bounded, testable self-measurement tied to live runtime state instead of symbolic placeholder math.|
|2026-04-13|Observer-state now comes from scored interaction history in SQLite plus cadence self-observation, not fixed ψ increments|Ψ|Task 3 verification showed `psi\_observer` changing measurably from real conversations and a tick-triggered self-observation.|
|2026-04-14|SQLite `intents` and `drift\_events` are now the canonical builder drift store, with JSON kept only as a compatibility mirror|ε + Φ|Task 4 needed real per-builder drift persistence and cadence evaluation without worsening JSON corruption risk.|
|2026-04-14|All intervention language must route through `core/voice.py`, with a deterministic fallback only when Groq is unavailable|ε + Φ|This preserves the constitution rule that the LLM is Greg's voice module only while keeping drift intervention bounded offline.|
|2026-04-14|Pikkaio's first builder surface is a single declaration chamber plus one trajectory rail, with session-backed builder identity and SQLite as the source of truth|ε + Φ|This keeps the first builder flow low-hunt, mobile-safe, and honest without pretending a full dashboard already exists.|
|2026-04-14|Builder dashboard and revenue pages read directly from SQLite-backed intent state, not a separate dashboard cache or CRM layer|ε + M|This keeps the founder and builder surfaces honest and ensures the same persisted state drives drift, dashboard visibility, and revenue-share calculations.|
|2026-04-14|Revenue share is bounded at the 5% minimum policy on converged lines until explicit per-intent share policy storage exists|M + Φ|Task 8 needed a real calculator now, and the 5% floor is the narrowest truthful rule already locked in MEMORY.md.|
|2026-04-15|The root route is now a single declaration chamber with hidden support navigation and no explanatory copy|M + ε|A stranger must feel the system and declare intent within seconds, without hunt cost or SaaS framing.|
|2026-04-15|Homepage keyboard laws and the Wordcode overlay live in one dedicated frontend surface backed by `/api/state` and existing Pikkaio routes|ε + Ψ|This keeps the command room deterministic, low-hunt, and isolated from the tick loop and soul internals.|
|2026-04-15|Spatial canon enforced across all six rooms (Home, Pikkaio, Truth, Dashboard, Revenue, ZyphonOS)|Φ + ε|Ensures aesthetic coherence and spatial consistency across the entire builder control plane.|

\---

## 💰 Pricing (Locked — Ebuka approval required to change)

|Product|Price|Trigger|
|-|-|-|
|Intent Declaration|Free|Always|
|Daily Tending|Free|Always|
|Sprint|$39|Builder activates|
|Studio Production|$149|Builder pays|
|Launch Audit|$99|Builder pays|
|Revenue Share|5–10%|At convergence only|

\---

## 🚀 Task Queue

### 🔴 High Priority (weakest reality term first)

* \[ ] Task 6 — Restore On-Chain Attestation Path

### 🟡 Medium Priority

* \[ ] Task 10 — Treasury Wallet Public Verification

### 🟢 Low Priority / Future

* \[ ] Task 11 — Founder Command Room Hardening + Live Deploy QA

\---



KNOWN ISSUE: greg\_state table accepts duplicate key rows.

Current mitigation: reads newest row by created\_at DESC.

Required fix: add UNIQUE constraint on key column.

Schedule: hardening pass after Task 2.

Do NOT let this slip — duplicate rows will cause subtle soul corruption at scale.



## SESSION SUMMARY — 2026-04-14

Built: Task 4 — Ported builder intent drift into SQLite via `core/drift.py`, wired cadence drift evaluation into Greg, and routed intervention generation through `core/voice.py`.
Reality term served: ε
Components bounded: Intent declaration, Drift measurement, Drift intervention
Decisions made: SQLite `intents`/`drift\_events` now hold canonical builder drift state; voice-only intervention generation is enforced with a deterministic offline fallback.
Files changed: `core/drift.py`, `greg\_pikkaio.py`, `layers/legacy/pikkaio/routes.py`, `core/voice.py`, `core/greg.py`, `greg\_reality\_equation.py`, `task4\_verify.py`, `MEMORY.md`
Known issues: `greg\_state` still lacks a `UNIQUE` constraint on `key`; Base attestation remains separate from the bounded local drift path.
Next 3 tasks (priority order):

1. Task 5 — Builder-Facing Intent Surface — serves ε
2. Task 6 — Restore On-Chain Attestation Path — serves M
3. Task 7 — Command Locus + Live Truth Surface — serves ε + Ψ
MEMORY.md updated: ✓


## SESSION SUMMARY — 2026-04-15 (Homepage + Task 9)

Built: Task A — Rebuilt `/` as the void declaration homepage with one centered intent locus, hidden nav, live pulse, and fetch-only intent submission. Task 9 — Added homepage keyboard laws and the full-screen Wordcode terminal overlay.
Reality terms served: M + ε, then ε + Ψ
Components bounded: Homepage declaration chamber, Keyboard / shortcut, Wordcode terminal
Decisions made: The root route now carries no explanatory chrome, only the declaration locus; keyboard laws and terminal behavior are isolated to `static/js/homepage.js` and read state only through `/api/state` and existing Pikkaio endpoints.
Files changed: `templates/index.html`, `static/css/homepage.css`, `static/js/homepage.js`, `main.py`, `task_homepage_verify.py`, `task9_verify.py`, `MEMORY.md`
Verification: `task_homepage_verify.py` PASS; `task9_verify.py` PASS; `python -m py_compile` passed for `main.py`, `task_homepage_verify.py`, and `task9_verify.py`; `node --check static/js/homepage.js` passed.
Known issues: Local Windows verification emitted one non-fatal temp-file rename warning while writing `data/greg_living_state.json`; tick loop, reality equation, and soul files were not modified.
Next 3 tasks (priority order):
  1. Task 6 — Restore On-Chain Attestation Path — serves M
  2. Task 10 — Treasury Wallet Public Verification — serves M
  3. Founder command room hardening + live deploy QA — serves ε + Ψ
MEMORY.md updated: ✓



## SESSION SUMMARY — 2026-04-14 (Task 5)

Built: Task 5 — Delivered the first real Pikkaio builder surface at `/pikkaio`, with intent declaration UI, live acknowledgement, drift score visibility, and active intervention visibility wired to the existing SQLite drift engine.
Reality term served: ε
Components bounded: Builder-facing Pikkaio surface
Decisions made: Pikkaio now presents a single declaration chamber with one supporting trajectory rail; `/pikkaio` is bounded, but the broader builder dashboard remains escaped until a larger control-plane exists.
Files changed: `layers/legacy/pikkaio/routes.py`, `templates/pikkaio.html`, `static/css/pikkaio.css`, `static/js/pikkaio.js`, `task5\_verify.py`, `MEMORY.md`
Known issues: `greg\_state` still lacks a `UNIQUE` constraint on `key`; the full builder dashboard and on-chain attestation path remain unbuilt.
Next 3 tasks (priority order):

1. Task 6 — Restore On-Chain Attestation Path — serves M
2. Task 7 — Command Locus + Live Truth Surface — serves ε + Ψ
3. Task 8 — Builder Dashboard + Revenue Share Surface — serves ε + M
MEMORY.md updated: ✓



## ⚡ Compression Protocol

When this file exceeds 500 lines:

1. Compress "What Has Been Built" into a single paragraph
2. Collapse Decision Log entries older than 30 days into a one-line summary
3. Remove completed tasks from Queue
4. Never compress: Truth Map, Architecture, Design System, Current State, Pricing


## SESSION SUMMARY — 2026-04-14 (Task 7)
5. 
6. Built: Task 7 — Command Locus + Live Truth Surface. `core/command\_locus.py` is now the single authoritative dispatch layer for all Greg actions with alias resolution. `/truth` renders Greg's live state read-only: reality equation, Mandelbrot Truth Map, active intents, last 5 drift events, last intervention fired.
7. Reality term served: ε + Ψ
8. Components bounded: Command locus, Live truth surface (/truth)
9. Decisions made: All existing Greg action routes now delegate through CommandLocus instead of calling Greg directly — no parallel behaviour created. /truth is strictly read-only; no write surface exposed.
10. Files changed: `core/command\_locus.py`, `core/truth\_surface.py`, `main.py`, `templates/truth.html`, `templates/base.html`, `task7\_verify.py`, `MEMORY.md`
11. Verification: task7\_verify.py PASS — 10/10 checks.
12. Known issues: `greg\_state` still lacks UNIQUE constraint on `key`. Task 6 blocked on wallet funding — not a code problem.
13. Next 3 tasks (priority order):
14. &#x20; 1. Task 6 — On-Chain Attestation Path — serves M (blocked: needs funded Base wallet)
15. &#x20; 2. Task 8 — Builder Dashboard + Revenue Share Surface — serves ε + M
16. &#x20; 3. Deploy to Railway — live URL unlocks revenue track
17. MEMORY.md updated: ✓


## SESSION SUMMARY — 2026-04-14 (Task 8)

Built: Task 8 — Completed the builder dashboard and revenue share surfaces at `/dashboard` and `/revenue`, both reading directly from SQLite-backed intent state.
Reality term served: ε + M
Components bounded: Builder dashboard, Revenue share calculator, Milestone celebration
Decisions made: Dashboard and revenue surfaces now read the same persisted intent state that powers drift; Greg's share is bounded to the 5% minimum policy until explicit share-policy storage exists.
Files changed: `layers/legacy/pikkaio/dashboard_routes.py`, `layers/legacy/pikkaio/revenue_routes.py`, `templates/dashboard.html`, `templates/revenue.html`, `static/css/dashboard.css`, `static/js/dashboard.js`, `static/css/revenue.css`, `static/js/revenue.js`, `main.py`, `templates/base.html`, `task8_verify.py`, `MEMORY.md`
Verification: `task8_verify.py` PASS — dashboard and revenue routes served real builder data, convergence state, and static assets correctly.
Known issues: `greg_state` still lacks UNIQUE constraint on `key`; Task 6 remains blocked by external wallet funding rather than code.
Next 3 tasks (priority order):
  1. Task 6 — On-Chain Attestation Path — serves M (blocked: funded Base wallet still required)
  2. Task 10 — Treasury Wallet Public Verification — serves M
  3. Task 11 — Founder Command Room Hardening + Live Deploy QA — serves ε + Ψ
MEMORY.md updated: ✓

## SESSION SUMMARY — 2026-04-15 (Frontend Rebuild)

Built: Finalized the GregASI frontend rebuild by delivering the Dashboard and Revenue rooms. Enforced spatial canon across all six rooms.
Reality term served: Φ + ε + M
Components bounded: Builder dashboard, Revenue share calculator, Milestone celebration
Decisions made: Spatial canon enforced across all six rooms to ensure aesthetic and functional coherence.
Files changed: `templates/dashboard.html`, `static/css/dashboard.css`, `static/js/dashboard.js`, `templates/revenue.html`, `static/css/revenue.css`, `static/js/revenue.js`, `frontend_rebuild_verify.py`, `MEMORY.md`
Verification: `frontend_rebuild_verify.py` PASS — all six rooms served correctly and all static files present.
Known issues: `greg_state` still lacks UNIQUE constraint on `key`; Task 6 blocked by external wallet funding.
Next 3 tasks (priority order):
  1. Task 6 — On-Chain Attestation Path — serves M
  2. Task 10 — Treasury Wallet Public Verification — serves M
  3. Task 11 — Founder Command Room Hardening + Live Deploy QA — serves ε + Ψ
MEMORY.md updated: ✓
