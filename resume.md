Here's RESUME.md — add this to every project root alongside the other constitution files:

---

```markdown
# RESUME.md — GregASI Session Resume Protocol
## Zero-waste continuation. Use this instead of full brief for incomplete tasks.
**Governed by GregASI Operational Constitution v1.1**

---

## When To Use This File

Use RESUME.md when:
- A task was interrupted mid-build (rate limit, context limit, crash)
- A task is >50% complete and you are continuing it
- You are fixing a specific bug in a bounded component

Do NOT use RESUME.md when:
- Starting a brand new task (use full TASK.md brief)
- Starting a new session on a task not yet begun
- You are unsure what state the codebase is in

---

## The Resume Prompt Format

When resuming, paste this exact format into Codex:

```
RESUME: [Task Name]

Read MEMORY.md only. Then read these files:
- [file 1 — only files directly needed]
- [file 2]
- [file 3]

Status: [X]% complete.

Already done:
- [what is confirmed built]
- [what is confirmed built]

Remaining:
- [exactly what is left]
- [exactly what is left]

Done when:
- [ ] [specific criterion]
- [ ] [specific criterion]
- [ ] task[N]_verify.py written and passing
- [ ] MEMORY.md Truth Map updated
- [ ] Session Summary written

Do not re-read constitution files. 
Do not re-explain what Greg is.
Build only what is listed under Remaining.
```

---

## Token Cost Comparison

| Session Type | Approx Token Cost | Use When |
|---|---|---|
| Full cold start | 3,000–4,000 tokens | New task, fresh session |
| Resume session | 800–1,200 tokens | Continuing incomplete task |
| Bug fix session | 400–600 tokens | Single file, known issue |

---

## Resume Prompt For Task 5 (Ready To Use Now)

```
RESUME: Task 5 — Pikkaio Builder Surface

Read MEMORY.md only. Then read these files:
- layers/legacy/pikkaio/routes.py
- templates/pikkaio/ (current template file)
- task5_verify.py (if it exists)

Status: ~90% complete.

Already done:
- Backend voice wiring — Pikkaio acknowledgement 
  through core/voice.py
- Route layer rewired — /pikkaio, /pikkaio/intent, 
  /pikkaio/status all in place
- Pikkaio logo asset copied into app
- Flask wiring complete

Remaining:
- Replace stub Pikkaio template with final declaration 
  chamber UI — dark, alive, Pikkaio-branded, mobile-friendly
- Write task5_verify.py
- Update MEMORY.md Truth Map
- Write session summary

Done when:
- [ ] UI served at /pikkaio — dark, alive, Pikkaio-branded
- [ ] Builder can declare intent through the UI
- [ ] Drift score and intervention visible on the surface
- [ ] Works on mobile
- [ ] task5_verify.py written and passing
- [ ] MEMORY.md Truth Map updated
- [ ] Session Summary written

Do not re-read constitution files.
Do not re-explain what Greg is.
Build only what is listed under Remaining.
```

---

## How To Write Your Own Resume Prompt

After any interrupted session, answer these four questions:

**1. What files did Codex actually touch?**
Check Codex's last message — it lists files edited.
Those are your "Read these files" list.

**2. What did Codex confirm as done?**
Any file Codex said it completed = Already done.

**3. Where exactly did it stop?**
Last action in Codex's final message = start of Remaining.

**4. What are the done criteria?**
Copy from original task brief, remove completed ones.

That's it. Four questions, one resume prompt, 
70% fewer tokens burned on re-orientation.

---

## Standing Rules

- Never include full constitution files in a resume session
- Never ask Codex to re-explain architecture it already knows
- Never resume without reading MEMORY.md first — 
  it is the single source of truth
- Always end every session (complete or interrupted) 
  with MEMORY.md updated — this makes every resume possible

---

*RESUME.md operates within GregASI Operational Constitution v1.1*
*Place in every project root alongside AGENTS.md, MEMORY.md, TASK.md*
*Amendments require Ebuka's written approval*
```