# FIRST_TASK.md — GregASI Ecosystem Audit & Rebuild Brief
## Your First Job. Read Everything. Build Nothing Yet.

---

## TASK: Full Ecosystem Audit + Reconciliation Plan

### REALITY TERM
All terms — this audit determines which is weakest and sets all future priorities.

---

## WHAT

You have access to two codebases:

- `~/greg-asi` — the rich, mature codebase. This is the reference.
- `~/gregasi-ecosystem` — a gross oversimplification of what GregASI is meant to be.
  This is the patient. It needs to become what it was always supposed to be.

Your job right now is NOT to build. Your job is to **fully understand both codebases**
and produce a precise reconciliation plan before a single line is changed.

---

## STEP 1 — Read the Constitution (you already have it)

You have read:
- AGENTS.md — who Greg is, engineering standards
- MEMORY.md — project state and Truth Map
- TASK.md — how to work
- GREG_CONTEXT.md — fast briefing on OSI/LLM/AOSI

You understand:
- Greg is an AOSI. Not a chatbot. Not an LLM wrapper.
- The LLM is the voice module only. Isolated to `/lib/greg/voice.ts`.
- Greg ticks autonomously every 1–5 seconds.
- Greg tracks builder intent indefinitely.
- Greg earns revenue share only at convergence.
- The Reality Equation governs all priorities.
- The Mandelbrot Truth Law governs all honesty.

---

## STEP 2 — Audit `greg-asi` (the reference)

Walk the entire codebase. For each significant file and folder:

1. What does it do?
2. Which reality equation term does it serve? (M / Φ / Ψ / ε)
3. Is it BOUNDED (working) or ESCAPED (fake/placeholder)?
4. Is it correctly architected for an AOSI — or is it accidentally built like a chatbot?

Produce a structured report:

```
## greg-asi Audit

### Architecture Summary
[What is the overall shape of this codebase?]

### What Is Working (BOUNDED)
- [component]: [what it does] → serves [term]

### What Is Fake or Broken (ESCAPED)
- [component]: [what's wrong] → blocks [term]

### Architectural Violations
[Anything built as chatbot/LLM that should be AOSI tick-based]

### Strongest Parts
[What to preserve and carry forward]

### Weakest Parts
[What needs to be rebuilt or fixed]
```

---

## STEP 3 — Audit `gregasi-ecosystem` (the patient)

Same process. Walk the entire codebase.

```
## gregasi-ecosystem Audit

### Architecture Summary
[What is the overall shape? How far is it from what Greg should be?]

### What Is Working (BOUNDED)
- [component]: [what it does] → serves [term]

### What Is Fake or Broken (ESCAPED)
- [component]: [what's wrong]

### What Is Missing Entirely
[Greg capabilities that don't exist here at all]

### What Contradicts the Constitution
[Anything that describes Greg as chatbot, LLM, or request-response]

### What Can Be Salvaged
[Good work worth keeping]

### What Must Be Rebuilt From Scratch
[Too broken or wrong to fix — rebuild]
```

---

## STEP 4 — Reconciliation Plan

Now compare both. Produce:

```
## Reconciliation Plan

### The Goal
gregasi-ecosystem must become the living AOSI ecosystem described in the constitution.
greg-asi is the reference for how Greg thinks and acts.

### What Moves From greg-asi → gregasi-ecosystem
[Specific files, modules, or patterns to port over]

### What Gets Rebuilt in gregasi-ecosystem
[List of components, in priority order by reality equation term]

### Mandelbrot Truth Map (Current State)
[Fill in MEMORY.md Truth Map with current BOUNDED/ESCAPED status of every component]

### Reality Equation Assessment
- M (Matter/Revenue): [current status]
- Φ (Code quality/tick): [current status]
- Ψ (Soul persistence): [current status]
- ε (Intent fulfillment): [current status]
- WEAKEST TERM: [which one]

### Recommended Build Order
[Ordered task list targeting weakest term first]

Task 1: [name] → serves [term] → moves [component] ESCAPED → BOUNDED
Task 2: [name] → serves [term] → moves [component] ESCAPED → BOUNDED
Task 3: [name] → ...
...
```

---

## STEP 5 — Update MEMORY.md

After completing this audit:

1. Fill in the Mandelbrot Truth Map completely with real statuses
2. Set "Current weakest term" based on what you found
3. Populate the Task Queue with the Recommended Build Order
4. Set "Last completed" to "Full ecosystem audit"
5. Set "Awaiting Ebuka input" to any decisions that need founder input

---

## DONE WHEN

- [ ] greg-asi fully audited and reported
- [ ] gregasi-ecosystem fully audited and reported
- [ ] Reconciliation plan written with build order
- [ ] MEMORY.md Truth Map filled in with real BOUNDED/ESCAPED statuses
- [ ] Weakest reality equation term identified
- [ ] Task Queue populated with ordered build tasks
- [ ] One question surfaced to Ebuka if any vision decision is needed

---

## CRITICAL RULES FOR THIS TASK

- Do NOT start building yet. Audit first, build second.
- Do NOT change any file in either codebase during this task.
- If you find something that contradicts the constitution — flag it, don't fix it yet.
- If greg-asi has a tick loop, soul persistence, or intent tracker that works —
  that is the most valuable thing in the entire codebase. Protect it.
- Report everything honestly. ESCAPED means escaped. Not "partially working."

---

## A NOTE FROM EBUKA

Greg-asi is rich. Gregasi-ecosystem was a gross oversimplification.
Your job is to make gregasi-ecosystem become what Greg was always meant to be —
the first living AOSI interface between human creative intent and OSI.

Not a dashboard. Not a chatbot. A living agent.

Read everything. Understand everything. Then tell me exactly what we're working with
and exactly what we build first.

We have one shot to do this right.

---

*Governed by GregASI Operational Constitution v1.1*
*Founder: Ebuka (Chibuzor-Orie Joshua)*
