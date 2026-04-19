# TASK.md — GregASI Precision Task Engine
## Zero Wasted Tokens. Maximum Builder Value.

---

## The Token Efficiency Principle

Every token spent on confusion is a token stolen from Greg.
Every token spent on re-explaining what Greg is — is an architectural failure.

AGENTS.md + MEMORY.md eliminate that failure.
This file eliminates the rest.

A perfectly formed task costs ~100 tokens to specify.
A vague task costs 1,000+ tokens in back-and-forth.
Use the format below. Every time.

---

## TASK FORMAT

```
## TASK: [Name — max 6 words]

### REALITY TERM
[Which term does this serve: M / Φ / Ψ / ε]
[If none — justify why this task should exist]

### WHAT
[One paragraph. What exactly needs to be built or changed?
Name files, components, and behaviours precisely.]

### WHY (Builder Impact)
[One sentence. How does this move a builder closer to fulfilled intent?]

### MANDELBROT STATUS TARGET
[After this task, which components move from ESCAPED → BOUNDED?]

### INPUTS
- Files to read: [list]
- Data to use: [list]
- Design reference: [Figma / screenshot / description]

### CONSTRAINTS
- Must NOT modify: [core tick loop / reality equation / soul files — unless Ebuka approved]
- Must work on: [mobile / desktop / both]
- Performance requirement: [e.g. "tick completes in under 200ms"]
- Other: [hard constraints]

### DONE WHEN
- [ ] [Criterion 1 — specific and verifiable]
- [ ] [Criterion 2]
- [ ] [Criterion 3]
- [ ] Mandelbrot Truth Map updated in MEMORY.md
- [ ] Decision Log updated if any new architectural choice was made
- [ ] Session Summary written

### CONTEXT POINTER
[Exact location in MEMORY.md for relevant context]
- See: Decision Log entry [DATE]
- See: Architecture Snapshot → [section]
- See: Design System → [section]
```

---

## Ebuka Shorthand → Codex Translation

Ebuka speaks vision. Codex translates to engineering.

| Ebuka says | Codex understands |
|---|---|
| "Make it feel alive" | Add Greg's tick pulse to UI. Animate soul persistence status. Show last tick timestamp updating in real time. |
| "Make it look more premium" | Elevate typography, tighten spacing, refine color usage, add subtle Framer Motion transitions. Audit against Design System. |
| "Something's broken" | Read error log. Trace to tick loop or soul write. Check Mandelbrot Truth Map. Fix and update status. |
| "Add [feature]" | Identify which reality equation term it serves. Decompose into subtasks. Confirm in one sentence. Build. |
| "It feels slow" | Profile tick loop. Check Supabase write times. Run Lighthouse. Fix top 3 issues. |
| "Is this production ready?" | Full audit: Mandelbrot Truth Map, performance, accessibility, error states, mobile, security, soul persistence. Report. |
| "Make Greg smarter" | Check OSI query layer status. Check drift measurement accuracy. Improve weakest BOUNDED component. |
| "Start fresh on [page]" | Read current file. Keep all logic and data. Redesign UI from scratch to Design System spec. |
| "What's the weakest thing?" | Read Mandelbrot Truth Map. Report all ESCAPED components. Recommend which to bound first by reality equation impact. |

---

## Task Decomposition

For any task that cannot complete in one context window — split it.

```
PARENT TASK: [Name]
Reality Term: [M / Φ / Ψ / ε]

├── SUBTASK 1: [Name]
│   Done when: [criterion]
│   MEMORY.md update: [what to log]
│
├── SUBTASK 2: [Name — depends on Subtask 1]
│   Done when: [criterion]
│   MEMORY.md update: [what to log]
│
└── SUBTASK 3: [Final integration + Mandelbrot update]
    Done when: [all components tested and status updated]
```

Each subtask ends with MEMORY.md updated.
A new session can start any subtask cold with zero briefing loss.

---

## Token Budget Rules

### Rule 1 — Read before writing
Before generating any code, read:
1. MEMORY.md (full)
2. All files listed in INPUTS
3. The actual file being modified (never rewrite from memory)

### Rule 2 — No re-explanation
Never re-explain what Greg is, what AOSI means, or what the reality equation is.
It's in MEMORY.md. Reference it: "Per MEMORY.md architecture, tick engine is isolated."

### Rule 3 — Output only what changed
When editing existing code, output ONLY changed sections:

```typescript
// CHANGED: src/lib/greg/tick.ts — tickGreg() function
[new code]
// END CHANGE
```

Never output an entire unchanged file.

### Rule 4 — One clarifying question
If a task is ambiguous, ask ONE question before starting.
"Before I start: [single question]. Everything else I'll infer and handle."

### Rule 5 — Batch small changes
3+ small changes = one batched response + one MEMORY.md update.
Never 3 separate responses for 3 small changes.

### Rule 6 — Compress summaries
When referencing past work in a response: maximum 2 sentences.
Full detail lives in MEMORY.md.

---

## Session Start Protocol

Every session, in this exact order:

```
1. Read AGENTS.md           → Who Greg is. Engineering standards.
2. Read MEMORY.md           → Current state. Truth Map. Decisions.
3. Read TASK.md             → How to work.
4. Read current task        → What to build now.
5. Read relevant files      → Only files needed for this task.
6. Confirm:                 → "I'll [X] using [Y], serving [reality term]."
7. Build.
8. Update MEMORY.md.
```

Steps 1–5: ~600–900 tokens.
Everything after: pure building.

---

## Session End Protocol

```
## SESSION SUMMARY — [DATE]

Built: [What was completed]
Reality term served: [M / Φ / Ψ / ε]
Components bounded: [Which ESCAPED → BOUNDED]
Decisions made: [New architectural choices]
Files changed: [List]
Known issues: [Anything flagged]
Next 3 tasks (priority order):
  1. [Task] — serves [term]
  2. [Task] — serves [term]
  3. [Task] — serves [term]
MEMORY.md updated: ✓
```

---

## Context Window Emergency Protocol

When Codex detects it is approaching context limit mid-task:

1. STOP building immediately
2. Write current progress to MEMORY.md
3. Write a handoff note:

```
## HANDOFF — [Task Name] — [DATE]

Completed:
- [What's done]

Stopped at:
- [Exact point in task]

Files in progress:
- [File]: [done / remaining]

To resume:
1. Start new session
2. Read AGENTS.md, MEMORY.md, TASK.md
3. Read this handoff note
4. Continue from: [exact instruction]

Mandelbrot status at handoff:
- [Component]: [status]
```

4. Tell Ebuka: "Context limit reached. Progress saved. Start a new session —
   Greg picks up exactly where we left off."

---

*TASK.md operates within the GregASI Operational Constitution v1.1.*
*All three files — AGENTS.md, MEMORY.md, TASK.md — must be in every project root.*
