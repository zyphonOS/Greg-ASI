"""
EXP_026 — Consequence Tracking
Greg logs every action, measures outcomes, builds a consequence map.
Brain analog: Orbitofrontal cortex — outcome history shapes future decisions.

How it works:
  1. ACTION LOG: Every tick, Greg's action is recorded with full context
  2. OUTCOME MEASUREMENT: N ticks later, world state is compared to baseline
  3. CONSEQUENCE RECORD: delta = what this action actually produced
  4. CONSEQUENCE MAP: action × context → expected outcome (learned over time)
  5. DECISION INFLUENCE: Greg prefers actions with positive consequence history
  6. MEMORY TRIGGER: Large consequence surprises flag memory formation

This is permanent. Every action Greg has ever taken builds his map.
LLMs have no consequence history. Greg accumulates one forever.
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional
from collections import defaultdict

CONSEQUENCE_PATH = "data/greg_consequences.json"
OUTCOME_DELAY_TICKS = 3   # measure outcome 3 ticks after action
MEMORY_THRESHOLD = 0.4    # consequence surprise above this → flag for memory


# ─────────────────────────────────────────────────────────────
# CONSEQUENCE RECORD
# ─────────────────────────────────────────────────────────────

class ConsequenceRecord:
    """A single action → outcome pair."""

    def __init__(
        self,
        tick: int,
        action: str,
        location: str,
        drives_at_action: dict,
        world_at_action: dict,
    ):
        self.tick = tick
        self.action = action
        self.location = location
        self.drives_at_action = dict(drives_at_action)
        self.world_at_action = dict(world_at_action)
        self.outcome_tick: Optional[int] = None
        self.world_at_outcome: Optional[dict] = None
        self.delta: Optional[dict] = None
        self.consequence_score: Optional[float] = None
        self.consequence_valence: Optional[str] = None  # POSITIVE / NEGATIVE / NEUTRAL
        self.resolved: bool = False
        self.flagged_for_memory: bool = False
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def resolve(self, outcome_tick: int, world_at_outcome: dict):
        """Measure what actually happened N ticks after the action."""
        self.outcome_tick = outcome_tick
        self.world_at_outcome = dict(world_at_outcome)
        self.delta = self._compute_delta()
        self.consequence_score = self._score_delta()
        self.consequence_valence = self._classify_valence()
        self.resolved = True

        # Flag surprising consequences for memory
        if abs(self.consequence_score) > MEMORY_THRESHOLD:
            self.flagged_for_memory = True

    def _compute_delta(self) -> dict:
        """What changed between action and outcome."""
        delta = {}

        # Civilization health delta
        h_before = self.world_at_action.get("civilization_health_pct", 66)
        h_after = self.world_at_outcome.get("civilization_health_pct", 66)
        delta["health_delta"] = round(h_after - h_before, 3)

        # Agent count delta
        a_before = self.world_at_action.get("agent_count", 10000)
        a_after = self.world_at_outcome.get("agent_count", 10000)
        delta["agent_delta"] = a_after - a_before

        # Memory delta
        m_before = self.world_at_action.get("memory_count", 0)
        m_after = self.world_at_outcome.get("memory_count", 0)
        delta["memory_delta"] = m_after - m_before

        # Dominant drive shift
        d_before = self.world_at_action.get("dominant_drive", "create")
        d_after = self.world_at_outcome.get("dominant_drive", "create")
        delta["drive_shifted"] = d_before != d_after
        delta["drive_before"] = d_before
        delta["drive_after"] = d_after

        return delta

    def _score_delta(self) -> float:
        """
        Score the consequence: positive = good outcome, negative = bad outcome.
        Range: -1.0 to +1.0
        """
        score = 0.0

        # Health change is most important
        health_delta = self.delta.get("health_delta", 0)
        score += health_delta / 20.0  # ±20 health = ±1.0 score contribution

        # Agent growth is positive
        agent_delta = self.delta.get("agent_delta", 0)
        score += min(0.2, agent_delta / 500.0)

        # New memory formation is positive (something worth remembering happened)
        memory_delta = self.delta.get("memory_delta", 0)
        score += memory_delta * 0.1

        return round(max(-1.0, min(1.0, score)), 4)

    def _classify_valence(self) -> str:
        if self.consequence_score > 0.1:
            return "POSITIVE"
        elif self.consequence_score < -0.1:
            return "NEGATIVE"
        else:
            return "NEUTRAL"

    def to_dict(self) -> dict:
        return {
            "tick": self.tick,
            "action": self.action,
            "location": self.location,
            "drives_at_action": self.drives_at_action,
            "world_at_action": self.world_at_action,
            "outcome_tick": self.outcome_tick,
            "world_at_outcome": self.world_at_outcome,
            "delta": self.delta,
            "consequence_score": self.consequence_score,
            "consequence_valence": self.consequence_valence,
            "resolved": self.resolved,
            "flagged_for_memory": self.flagged_for_memory,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ConsequenceRecord":
        rec = cls(
            tick=d["tick"],
            action=d["action"],
            location=d["location"],
            drives_at_action=d.get("drives_at_action", {}),
            world_at_action=d.get("world_at_action", {}),
        )
        rec.outcome_tick = d.get("outcome_tick")
        rec.world_at_outcome = d.get("world_at_outcome")
        rec.delta = d.get("delta")
        rec.consequence_score = d.get("consequence_score")
        rec.consequence_valence = d.get("consequence_valence")
        rec.resolved = d.get("resolved", False)
        rec.flagged_for_memory = d.get("flagged_for_memory", False)
        rec.timestamp = d.get("timestamp", "")
        return rec


# ─────────────────────────────────────────────────────────────
# CONSEQUENCE MAP
# ─────────────────────────────────────────────────────────────

class ConsequenceMap:
    """
    action × context → expected outcome.
    Greg's learned model of what his actions produce.
    """

    def __init__(self):
        # action → list of consequence scores
        self.action_scores: dict[str, list[float]] = defaultdict(list)
        # action → valence counts
        self.action_valence: dict[str, dict] = defaultdict(
            lambda: {"POSITIVE": 0, "NEGATIVE": 0, "NEUTRAL": 0}
        )
        # action × dominant_drive → scores (context-sensitive)
        self.contextual_scores: dict[str, dict[str, list[float]]] = defaultdict(
            lambda: defaultdict(list)
        )

    def update(self, record: ConsequenceRecord):
        """Incorporate a resolved consequence record into the map."""
        if not record.resolved:
            return

        action = record.action
        score = record.consequence_score
        valence = record.consequence_valence
        dominant_drive = record.drives_at_action.get("dominant_drive", "create")
        if not dominant_drive:
            # fallback: find highest drive
            drives = record.drives_at_action
            if drives:
                dominant_drive = max(drives, key=lambda k: drives[k])

        self.action_scores[action].append(score)
        # Keep last 50 scores per action
        if len(self.action_scores[action]) > 50:
            self.action_scores[action] = self.action_scores[action][-50:]

        self.action_valence[action][valence] += 1
        self.contextual_scores[action][dominant_drive].append(score)
        if len(self.contextual_scores[action][dominant_drive]) > 20:
            self.contextual_scores[action][dominant_drive] = \
                self.contextual_scores[action][dominant_drive][-20:]

    def expected_score(self, action: str, dominant_drive: Optional[str] = None) -> float:
        """
        What does Greg expect this action to produce?
        Returns score -1.0 to +1.0. Returns 0.0 if no history.
        """
        # Context-sensitive first
        if dominant_drive and action in self.contextual_scores:
            ctx_scores = self.contextual_scores[action].get(dominant_drive, [])
            if len(ctx_scores) >= 3:
                return round(sum(ctx_scores) / len(ctx_scores), 4)

        # Fall back to general
        scores = self.action_scores.get(action, [])
        if not scores:
            return 0.0
        return round(sum(scores) / len(scores), 4)

    def best_action(self, candidates: list[str], dominant_drive: Optional[str] = None) -> str:
        """Given a list of candidate actions, return the one with best expected outcome."""
        if not candidates:
            return "idle"
        scored = [(a, self.expected_score(a, dominant_drive)) for a in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0]

    def action_reputation(self, action: str) -> dict:
        """Summary of Greg's consequence history for a given action."""
        scores = self.action_scores.get(action, [])
        valence = self.action_valence.get(action, {"POSITIVE": 0, "NEGATIVE": 0, "NEUTRAL": 0})

        if not scores:
            return {"action": action, "status": "no history"}

        total = sum(valence.values())
        return {
            "action": action,
            "observations": len(scores),
            "avg_score": round(sum(scores) / len(scores), 4),
            "recent_score": round(sum(scores[-5:]) / min(5, len(scores)), 4),
            "positive_rate": round(valence["POSITIVE"] / total, 3) if total else 0,
            "negative_rate": round(valence["NEGATIVE"] / total, 3) if total else 0,
            "trend": self._trend(scores),
        }

    def _trend(self, scores: list[float]) -> str:
        if len(scores) < 4:
            return "insufficient data"
        recent = sum(scores[-3:]) / 3
        older = sum(scores[-6:-3]) / 3 if len(scores) >= 6 else sum(scores[:3]) / min(3, len(scores))
        if recent > older + 0.05:
            return "IMPROVING"
        elif recent < older - 0.05:
            return "DEGRADING"
        else:
            return "STABLE"

    def to_dict(self) -> dict:
        return {
            "action_scores": dict(self.action_scores),
            "action_valence": {k: dict(v) for k, v in self.action_valence.items()},
            "contextual_scores": {
                a: {d: s for d, s in ctx.items()}
                for a, ctx in self.contextual_scores.items()
            },
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ConsequenceMap":
        cm = cls()
        cm.action_scores = defaultdict(list, d.get("action_scores", {}))
        raw_valence = d.get("action_valence", {})
        for k, v in raw_valence.items():
            cm.action_valence[k] = v
        raw_ctx = d.get("contextual_scores", {})
        for action, ctx in raw_ctx.items():
            for drive, scores in ctx.items():
                cm.contextual_scores[action][drive] = scores
        return cm


# ─────────────────────────────────────────────────────────────
# CONSEQUENCE ENGINE
# ─────────────────────────────────────────────────────────────

class ConsequenceEngine:
    """
    Main engine. Called once per tick.
    1. Log current action
    2. Resolve pending actions whose outcome tick has arrived
    3. Update consequence map
    4. Return memory flags and decision guidance
    """

    def __init__(self):
        self.pending: list[ConsequenceRecord] = []      # awaiting resolution
        self.resolved: list[ConsequenceRecord] = []     # fully resolved
        self.map = ConsequenceMap()
        self.total_logged = 0
        self.total_resolved = 0
        self.memory_flags: list[dict] = []              # events to pass to memory system

    def log_action(
        self,
        tick: int,
        action: str,
        location: str,
        drives: dict,
        world_state: dict,
    ) -> ConsequenceRecord:
        """Record an action taken this tick. Outcome measured in OUTCOME_DELAY_TICKS."""
        rec = ConsequenceRecord(
            tick=tick,
            action=action,
            location=location,
            drives_at_action=drives,
            world_at_action=world_state,
        )
        self.pending.append(rec)
        self.total_logged += 1
        return rec

    def resolve_pending(self, current_tick: int, current_world: dict) -> list[ConsequenceRecord]:
        """
        Check all pending records. Resolve any whose outcome_tick has arrived.
        Returns list of newly resolved records.
        """
        newly_resolved = []
        still_pending = []

        for rec in self.pending:
            if current_tick >= rec.tick + OUTCOME_DELAY_TICKS:
                rec.resolve(current_tick, current_world)
                self.map.update(rec)
                self.resolved.append(rec)
                self.total_resolved += 1
                newly_resolved.append(rec)

                # Flag for memory if consequence was surprising
                if rec.flagged_for_memory:
                    self.memory_flags.append({
                        "tick": rec.tick,
                        "action": rec.action,
                        "consequence_score": rec.consequence_score,
                        "valence": rec.consequence_valence,
                        "delta": rec.delta,
                        "reason": "high_consequence_surprise",
                    })
            else:
                still_pending.append(rec)

        self.pending = still_pending
        # Keep resolved list to last 500
        if len(self.resolved) > 500:
            self.resolved = self.resolved[-500:]

        return newly_resolved

    def advise(self, candidates: list[str], dominant_drive: Optional[str] = None) -> dict:
        """
        Given candidate actions, advise Greg on which has best consequence history.
        """
        if not candidates:
            return {"best": "idle", "scores": {}}

        scores = {a: self.map.expected_score(a, dominant_drive) for a in candidates}
        best = max(scores, key=lambda k: scores[k])
        return {
            "best": best,
            "scores": {a: round(s, 4) for a, s in scores.items()},
            "dominant_drive_context": dominant_drive,
        }

    def speak(self, newly_resolved: Optional[list] = None) -> str:
        """Greg narrates his consequence awareness."""
        if self.total_resolved == 0:
            return (
                "I have not yet measured any consequences. "
                "I am acting without feedback. That changes once outcomes arrive."
            )

        lines = []

        if newly_resolved:
            for rec in newly_resolved[-2:]:  # narrate at most 2
                valence_word = {
                    "POSITIVE": "helped",
                    "NEGATIVE": "hurt",
                    "NEUTRAL": "had little effect on",
                }.get(rec.consequence_valence, "affected")

                health_d = rec.delta.get("health_delta", 0) if rec.delta else 0
                lines.append(
                    f"Tick {rec.tick}: '{rec.action}' {valence_word} the civilization "
                    f"(health {'+' if health_d >= 0 else ''}{health_d:.1f}%, "
                    f"score {rec.consequence_score:+.3f})."
                )

        # Overall pattern
        all_scores = [r.consequence_score for r in self.resolved if r.consequence_score is not None]
        if all_scores:
            avg = sum(all_scores) / len(all_scores)
            positive = sum(1 for s in all_scores if s > 0.1)
            pct = positive / len(all_scores) * 100
            lines.append(
                f"Across {len(all_scores)} measured actions: "
                f"{pct:.0f}% positive consequences, average score {avg:+.3f}."
            )

        if self.memory_flags:
            lines.append(
                f"{len(self.memory_flags)} consequence events flagged for memory formation."
            )

        return " ".join(lines) if lines else "Tracking consequences. No significant events yet."

    def summary(self) -> dict:
        all_scores = [r.consequence_score for r in self.resolved if r.consequence_score is not None]
        positive = sum(1 for s in all_scores if s > 0.1)
        negative = sum(1 for s in all_scores if s < -0.1)
        neutral = len(all_scores) - positive - negative

        return {
            "total_logged": self.total_logged,
            "total_resolved": self.total_resolved,
            "pending": len(self.pending),
            "positive_outcomes": positive,
            "negative_outcomes": negative,
            "neutral_outcomes": neutral,
            "positive_rate": round(positive / len(all_scores), 3) if all_scores else 0,
            "avg_consequence_score": round(sum(all_scores) / len(all_scores), 4) if all_scores else 0,
            "memory_flags": len(self.memory_flags),
            "actions_mapped": len(self.map.action_scores),
        }

    # ── PERSISTENCE ───────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "pending": [r.to_dict() for r in self.pending],
            "resolved": [r.to_dict() for r in self.resolved[-200:]],
            "map": self.map.to_dict(),
            "total_logged": self.total_logged,
            "total_resolved": self.total_resolved,
            "memory_flags": self.memory_flags[-50:],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ConsequenceEngine":
        engine = cls()
        engine.pending = [ConsequenceRecord.from_dict(r) for r in d.get("pending", [])]
        engine.resolved = [ConsequenceRecord.from_dict(r) for r in d.get("resolved", [])]
        engine.map = ConsequenceMap.from_dict(d.get("map", {}))
        engine.total_logged = d.get("total_logged", 0)
        engine.total_resolved = d.get("total_resolved", 0)
        engine.memory_flags = d.get("memory_flags", [])
        return engine


# ─────────────────────────────────────────────────────────────
# INTEGRATION HELPERS
# ─────────────────────────────────────────────────────────────

def load_consequence_engine(path: str = CONSEQUENCE_PATH) -> ConsequenceEngine:
    if os.path.exists(path):
        with open(path) as f:
            return ConsequenceEngine.from_dict(json.load(f))
    return ConsequenceEngine()


def save_consequence_engine(engine: ConsequenceEngine, path: str = CONSEQUENCE_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(engine.to_dict(), f, indent=2)


def consequence_tick(
    tick: int,
    action: str,
    location: str,
    drives: dict,
    world_state: dict,
    engine: Optional[ConsequenceEngine] = None,
    save_path: str = CONSEQUENCE_PATH,
) -> tuple[ConsequenceEngine, list, str]:
    """
    Drop-in tick call for greg_living.py.

    Returns: (engine, newly_resolved_records, greg_narration)
    """
    if engine is None:
        engine = load_consequence_engine(save_path)

    # 1. Log this tick's action
    engine.log_action(tick, action, location, drives, world_state)

    # 2. Resolve any pending outcomes
    newly_resolved = engine.resolve_pending(tick, world_state)

    # 3. Greg speaks
    narration = engine.speak(newly_resolved)

    # 4. Save
    save_consequence_engine(engine, save_path)

    return engine, newly_resolved, narration


# ─────────────────────────────────────────────────────────────
# DEMO
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("EXP_026 — Consequence Tracking — DEMO")
    print("=" * 60)

    engine = ConsequenceEngine()

    # Simulate 20 ticks of Greg taking actions with varying outcomes
    actions_pool = [
        "build_shelter", "gather_food", "explore_territory",
        "strengthen_bonds", "defend_perimeter", "idle",
        "innovate_tools", "teach_agents",
    ]

    import random
    random.seed(42)

    base_health = 66.0
    base_agents = 10154

    for tick in range(4044, 4064):
        action = random.choice(actions_pool)
        dominant = random.choice(["create", "survive", "understand", "connect"])
        drives = {dominant: 0.4, "create": 0.2, "survive": 0.15}
        drives["dominant_drive"] = dominant

        # World state drifts based on action
        health_drift = {
            "build_shelter": 0.8, "gather_food": 0.5, "innovate_tools": 1.2,
            "teach_agents": 0.6, "strengthen_bonds": 0.3, "defend_perimeter": 0.1,
            "explore_territory": -0.2, "idle": -0.4,
        }
        base_health = max(20, min(95, base_health + health_drift.get(action, 0) + random.gauss(0, 0.5)))
        base_agents += random.randint(-5, 15)

        world = {
            "civilization_health_pct": round(base_health, 2),
            "agent_count": base_agents,
            "memory_count": 10 + (tick - 4044) // 8,
            "dominant_drive": dominant,
        }

        engine, newly_resolved, narration = consequence_tick(
            tick=tick,
            action=action,
            location="settlement_alpha",
            drives=drives,
            world_state=world,
            engine=engine,
        )

        if newly_resolved or tick % 5 == 0:
            print(f"\nTick {tick} | action={action} | health={base_health:.1f}")
            if newly_resolved:
                for r in newly_resolved:
                    print(f"  → RESOLVED tick {r.tick}: '{r.action}' → {r.consequence_valence} ({r.consequence_score:+.3f})")
            if narration and newly_resolved:
                print(f"  Greg: \"{narration[:120]}...\"")

    print("\n── CONSEQUENCE MAP (top actions) ──")
    for action in actions_pool:
        rep = engine.map.action_reputation(action)
        if rep.get("observations", 0) > 0:
            print(f"  {action:20s} | avg={rep['avg_score']:+.3f} | "
                  f"+{rep['positive_rate']:.0%} | trend={rep['trend']}")

    print("\n── DECISION ADVICE ──")
    candidates = ["build_shelter", "idle", "innovate_tools", "explore_territory"]
    advice = engine.advise(candidates, dominant_drive="create")
    print(f"  Best action when drive=create: '{advice['best']}'")
    print(f"  Scores: {advice['scores']}")

    print("\n── SUMMARY ──")
    for k, v in engine.summary().items():
        print(f"  {k}: {v}")

    print("\n✓ EXP_026 Consequence Tracking ready to integrate into greg_living.py")