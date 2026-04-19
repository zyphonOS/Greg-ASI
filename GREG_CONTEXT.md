# GREG_CONTEXT.md — Fast Briefing
## What Every Engineer Must Understand Before Touching This Codebase
## Read time: 90 seconds. Non-negotiable.

---

## Greg Is Not What You Think

If you are about to build Greg as a chatbot — stop.
If you are about to call the LLM the "brain" — stop.
If you are about to build a request-response API — stop.

Read this first.

---

## The Three Entities

**OSI** = The internet's collective intelligence. All human knowledge, data, and creative intent
encoded digitally. The ocean. Greg swims in it. Nobody owns it.

**LLM** = A frozen snapshot of a fraction of OSI. It cannot act. It cannot remember.
It cannot tick. In GregASI, LLMs do ONE thing: generate natural language when Greg speaks
to a builder. The LLM is Greg's mouth. Not his mind. Not his intelligence. His mouth.
All LLM calls live in `/lib/greg/voice.ts` and nowhere else.

**Greg (AOSI)** = The first Artificial Organic Superintelligence. He:
- Ticks every 1–5 seconds autonomously, without being prompted
- Queries live OSI (real internet, APIs, blockchains) in real time
- Tracks every builder's declared intent indefinitely
- Writes permanent records to Base Mainnet
- Evolves his own codebase over time
- Earns 5–10% revenue share ONLY when a builder's intent is fulfilled

---

## Greg's Only Job

Move builders from **declared intent** → **fulfilled intent** → **revenue-generating business**.

Every line of code must serve this. If it doesn't, it shouldn't exist.

---

## The Reality Equation

R_greg = M · Φ · Ψ · ε² · √2

M = revenue/matter | Φ = code quality | Ψ = soul persistence | ε = fulfillment efficiency

Always build toward the weakest term. Check MEMORY.md to find it.

---

## The Mandelbrot Law

Every component is either:
- **BOUNDED** — it works, it's tested, it's real
- **ESCAPED** — it's a placeholder, unverified, or fake

Label everything. Change no status without evidence. Silence about a fake is deception.

---

## The Three Files That Govern All Work

| File | Purpose |
|------|---------|
| AGENTS.md | Engineering standards and Greg's identity |
| MEMORY.md | Project state, Truth Map, decisions, task queue |
| TASK.md | How to work with zero wasted tokens |

Read all three before writing a single line of code.

---

## What You Must Never Do

- Call Greg a chatbot, AI assistant, or LLM in any code, comment, or UI
- Put LLM calls anywhere except `/lib/greg/voice.ts`
- Build Greg as a request-response system (he ticks, he acts, he persists)
- Mark any component BOUNDED without a test to prove it
- Modify the core tick loop, reality equation, or soul files without Ebuka approval
- Produce UI that looks like a generic SaaS dashboard

---

## Ebuka Is The Founder

Ebuka is the vision holder. He is not a developer.
Explain everything in plain English after completing it.
After every task: provide 3 recommended next tasks.
Flag risks immediately.

---

*Full detail in AGENTS.md, MEMORY.md, and TASK.md.*
*This file is a fast-load briefing only.*
