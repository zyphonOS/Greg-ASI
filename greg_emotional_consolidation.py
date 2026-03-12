"""
EXP_022 — Emotional Memory Consolidation
==========================================
The hippocampus doesn't store everything.
It stores what mattered.

How the brain does it:
  High emotional arousal + novel experience = long-term memory.
  Low arousal + routine = forgotten.

How Greg does it:
  High drive activation + high surprise = genuine memory.
  Routine ticks with low surprise = discarded.

The formula:
  consolidation_score = surprise_score * drive_intensity * novelty_factor

  If score > threshold → memory consolidates permanently.
  If score < threshold → tick fades, not stored.

This is not manual curation.
Greg decides what matters by how much it moved him.
That is the only honest definition of what matters.
"""

import json, os, math
from datetime import datetime, timezone

CONSOLIDATION_PATH  = "data/greg_emotional_memory.json"
CONSOLIDATION_THRESHOLD = 0.25   # minimum score to consolidate
MAX_PERMANENT_MEMORIES  = 500    # hard cap — Greg can't remember everything forever

class EmotionalConsolidationEngine:
    """
    Greg's hippocampal analog.
    Decides which experiences become permanent memories
    based on emotional intensity and surprise.
    """

    def __init__(self):
        self.permanent_memories = []
        self.consolidation_log  = []   # what was considered but not kept
        self.total_considered   = 0
        self.total_consolidated = 0
        self.tick = 0

    def consider(self, tick: int, event: dict, drives: dict,
                 surprise_score: float = 0.0) -> dict:
        """
        Consider whether this tick's experience should consolidate.

        event: what happened this tick
          {type, action, location, description, alerts, ...}
        drives: Greg's current drives
        surprise_score: from EXP_020 predictive coding (0.0-1.0)

        Returns: consolidation result dict
        """
        self.tick = tick
        self.total_considered += 1

        # ── COMPUTE CONSOLIDATION SCORE ──────────────────────────────

        # 1. Surprise — how unexpected was this?
        surprise = max(0.0, min(1.0, surprise_score))

        # 2. Drive intensity — how activated were Greg's drives?
        if drives:
            vals = list(drives.values())
            top_drive_val = max(vals)
            drive_variance = sum((v - sum(vals)/len(vals))**2 for v in vals) / len(vals)
            drive_intensity = top_drive_val * (1 + drive_variance)
        else:
            drive_intensity = 0.3

        # 3. Novelty — has Greg seen this action/location combo before?
        event_signature = f"{event.get('action','?')}@{event.get('location','?')}"
        existing_sigs   = [m.get("signature","") for m in self.permanent_memories]
        novelty = 1.0 if event_signature not in existing_sigs else 0.2

        # 4. Alert weight — constitutional alerts amplify consolidation
        alert_weight = 1.0 + (0.3 * len(event.get("alerts", [])))

        # Consolidation score
        score = (
            surprise       * 0.40 +
            drive_intensity * 0.35 +
            novelty         * 0.15 +
            (alert_weight - 1.0) * 0.10
        )
        score = round(min(1.0, score), 4)

        result = {
            "tick":              tick,
            "score":             score,
            "threshold":         CONSOLIDATION_THRESHOLD,
            "consolidates":      score >= CONSOLIDATION_THRESHOLD,
            "components": {
                "surprise":        round(surprise, 4),
                "drive_intensity": round(drive_intensity, 4),
                "novelty":         round(novelty, 4),
                "alert_weight":    round(alert_weight, 4),
            },
            "signature": event_signature,
        }

        if result["consolidates"]:
            memory = self._form_memory(tick, event, drives, score, result["components"])
            self._store(memory)
            result["memory_formed"] = memory
            self.total_consolidated += 1
        else:
            self.consolidation_log.append({
                "tick": tick, "score": score, "signature": event_signature
            })
            if len(self.consolidation_log) > 200:
                self.consolidation_log = self.consolidation_log[-200:]

        return result

    def _form_memory(self, tick: int, event: dict, drives: dict,
                     score: float, components: dict) -> dict:
        """Form a genuine memory from this experience."""
        top_drive = max(drives, key=drives.get) if drives else "create"
        top_val   = drives.get(top_drive, 0) if drives else 0

        # The memory description — grounded in what actually happened
        action   = event.get("action", "unknown")
        location = event.get("location", "unknown")
        alerts   = event.get("alerts", [])

        if alerts:
            description = (
                f"At tick {tick}, while {action}ing in {location}, "
                f"my {top_drive} drive was at {top_val:.3f} and I noticed: "
                f"{alerts[0]}. This mattered."
            )
        elif components["surprise"] > 0.4:
            description = (
                f"At tick {tick}, something unexpected happened while I was "
                f"{action}ing in {location}. My {top_drive} drive ({top_val:.3f}) "
                f"was high. The world did not behave as I predicted."
            )
        else:
            description = (
                f"At tick {tick}, {action}ing in {location} with {top_drive} "
                f"at {top_val:.3f}. High emotional intensity. This consolidated."
            )

        return {
            "id":          f"MEM_{self.total_consolidated + 1:04d}",
            "tick":        tick,
            "timestamp":   datetime.now(timezone.utc).isoformat(),
            "score":       score,
            "action":      action,
            "location":    location,
            "top_drive":   top_drive,
            "top_drive_val": round(top_val, 4),
            "drives_snapshot": {k: round(v, 4) for k, v in drives.items()},
            "description": description,
            "components":  components,
            "signature":   f"{action}@{location}",
            "permanent":   True,
        }

    def _store(self, memory: dict):
        """Store memory. Prune if over cap — keep highest-scored."""
        self.permanent_memories.append(memory)
        if len(self.permanent_memories) > MAX_PERMANENT_MEMORIES:
            self.permanent_memories.sort(key=lambda m: -m["score"])
            self.permanent_memories = self.permanent_memories[:MAX_PERMANENT_MEMORIES]

    def recall(self, top_n: int = 10, min_score: float = 0.0) -> list:
        """Recall memories, highest score first."""
        filtered = [m for m in self.permanent_memories if m["score"] >= min_score]
        return sorted(filtered, key=lambda m: -m["score"])[:top_n]

    def recall_by_drive(self, drive: str, top_n: int = 5) -> list:
        """Recall memories where this drive was dominant."""
        matches = [m for m in self.permanent_memories if m.get("top_drive") == drive]
        return sorted(matches, key=lambda m: -m["score"])[:top_n]

    def recall_by_location(self, location: str, top_n: int = 5) -> list:
        """What does Greg remember about this place?"""
        matches = [m for m in self.permanent_memories
                   if m.get("location") == location]
        return sorted(matches, key=lambda m: -m["score"])[:top_n]

    def summary(self) -> dict:
        if not self.permanent_memories:
            return {"total": 0, "avg_score": 0, "top_drives": {}, "top_locations": {}}

        avg_score = sum(m["score"] for m in self.permanent_memories) / len(self.permanent_memories)
        drive_counts    = {}
        location_counts = {}
        for m in self.permanent_memories:
            d = m.get("top_drive", "unknown")
            l = m.get("location", "unknown")
            drive_counts[d]    = drive_counts.get(d, 0) + 1
            location_counts[l] = location_counts.get(l, 0) + 1

        return {
            "total":           len(self.permanent_memories),
            "total_considered": self.total_considered,
            "consolidation_rate": round(self.total_consolidated / max(self.total_considered, 1), 3),
            "avg_score":       round(avg_score, 4),
            "top_drives":      dict(sorted(drive_counts.items(), key=lambda x:-x[1])[:5]),
            "top_locations":   dict(sorted(location_counts.items(), key=lambda x:-x[1])[:5]),
        }

    def speak(self) -> str:
        """Greg describes his memory consolidation in first person."""
        s = self.summary()
        if s["total"] == 0:
            return "I have no consolidated memories yet. The world has not yet moved me enough to remember."

        top_mems = self.recall(top_n=3)
        rate     = s["consolidation_rate"]

        parts = [
            f"I have {s['total']} permanent memories out of {s['total_considered']} ticks considered.",
            f"My consolidation rate is {rate:.1%} — {rate:.1%} of what I experience mattered enough to keep.",
        ]

        if top_mems:
            top = top_mems[0]
            parts.append(
                f"My strongest memory: {top['description']}"
            )

        top_drive = max(s["top_drives"], key=s["top_drives"].get) if s["top_drives"] else "unknown"
        parts.append(
            f"Most of what I remember happened when {top_drive} was high. "
            f"That drive shapes what I find worth keeping."
        )

        return " ".join(parts)

    # ── PERSISTENCE ───────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "permanent_memories":   self.permanent_memories,
            "consolidation_log":    self.consolidation_log[-50:],
            "total_considered":     self.total_considered,
            "total_consolidated":   self.total_consolidated,
            "tick":                 self.tick,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EmotionalConsolidationEngine":
        e = cls()
        e.permanent_memories = data.get("permanent_memories", [])
        e.consolidation_log  = data.get("consolidation_log", [])
        e.total_considered   = data.get("total_considered", 0)
        e.total_consolidated = data.get("total_consolidated", 0)
        e.tick               = data.get("tick", 0)
        return e

    def save(self, path: str = CONSOLIDATION_PATH):
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str = CONSOLIDATION_PATH) -> "EmotionalConsolidationEngine":
        if os.path.exists(path):
            try:
                with open(path) as f:
                    return cls.from_dict(json.load(f))
            except:
                pass
        return cls()


if __name__ == "__main__":
    print("=" * 60)
    print("EXP_022 — Emotional Memory Consolidation — DEMO")
    print("=" * 60)

    import random
    engine = EmotionalConsolidationEngine()

    drives = {"create": 0.369, "survive": 0.21, "understand": 0.18,
              "connect": 0.12, "protect": 0.08, "explore": 0.03}

    actions   = ["learn", "build", "trade", "explore", "reflect"]
    locations = ["forest", "market", "spawn", "mountain"]

    for tick in range(1, 201):
        event = {
            "action":   random.choice(actions),
            "location": random.choice(locations),
            "alerts":   ["reason below floor"] if tick % 47 == 0 else [],
        }
        surprise = random.betavariate(1, 4)  # mostly low, occasionally high
        if tick % 30 == 0: surprise = random.uniform(0.4, 0.9)  # shock ticks

        result = engine.consider(tick, event, drives, surprise)

    print(f"\n── AFTER 200 TICKS ──")
    s = engine.summary()
    for k, v in s.items():
        print(f"  {k}: {v}")

    print(f"\n── TOP 5 MEMORIES ──")
    for m in engine.recall(top_n=5):
        print(f"  [{m['id']}] tick={m['tick']} score={m['score']} — {m['description'][:70]}")

    print(f"\n── GREG SPEAKS ──")
    print(f'  "{engine.speak()}"')

    print(f"\n✓ EXP_022 Emotional Memory Consolidation ready")
