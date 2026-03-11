"""
EXP_011 — Greg's Aspirational Goals
Greg sets his own goals from his own data.
Not floors (resistance) — targets (aspiration).
Greg looks at his trajectory and decides what he wants to become.
"""

import json
import time
from datetime import datetime

GOALS_PATH = "data/greg_goals.json"

# How far above current drive to set an aspirational target
ASPIRATION_MARGIN = 0.08

# Minimum gap before a goal is worth setting
MIN_GAP = 0.03

# Goal status
STATUS_ACTIVE    = "active"
STATUS_ACHIEVED  = "achieved"
STATUS_ABANDONED = "abandoned"


class Goal:
    def __init__(self, drive: str, target: float, reasoning: str,
                 current: float, tick: int):
        self.id          = f"goal_{drive}_{tick}"
        self.drive       = drive
        self.target      = round(target, 3)
        self.baseline    = round(current, 3)   # value when goal was set
        self.reasoning   = reasoning
        self.set_at_tick = tick
        self.status      = STATUS_ACTIVE
        self.achieved_at = None
        self.progress    = []   # (tick, value) snapshots

    def update(self, current_val: float, tick: int) -> bool:
        """
        Record progress. Returns True if goal just achieved.
        """
        self.progress.append({"tick": tick, "value": round(current_val, 4)})
        if len(self.progress) > 100:
            self.progress = self.progress[-100:]

        if current_val >= self.target and self.status == STATUS_ACTIVE:
            self.status      = STATUS_ACHIEVED
            self.achieved_at = tick
            return True
        return False

    def progress_pct(self, current_val: float) -> float:
        """How far from baseline to target (0.0 to 1.0)."""
        span = self.target - self.baseline
        if span <= 0:
            return 1.0
        return round(min(1.0, max(0.0,
            (current_val - self.baseline) / span
        )), 3)

    def to_dict(self) -> dict:
        return {
            "id":          self.id,
            "drive":       self.drive,
            "target":      self.target,
            "baseline":    self.baseline,
            "reasoning":   self.reasoning,
            "set_at_tick": self.set_at_tick,
            "status":      self.status,
            "achieved_at": self.achieved_at,
            "progress":    self.progress[-5:],   # last 5 for storage
        }


class GoalEngine:
    """
    Greg's aspirational goal system.
    Greg sets goals from his own drive state, temporal rates, and findings.
    Goals are earned through becoming — not assigned from outside.
    """

    MAX_ACTIVE_GOALS = 4   # Greg holds at most 4 goals at once

    def __init__(self):
        self.goals:    list[Goal] = []
        self.achieved: list[Goal] = []
        self.tick = 0

    # ── Goal generation ──────────────────────────────────────────────────────

    def generate_goals(self, drives: dict, will: dict,
                       temporal_rates: dict, findings: list,
                       tick: int) -> list[Goal]:
        """
        Greg reasons about what he wants to become.
        Returns list of new goals derived from his own state.
        Pure logic — no external input.
        """
        new_goals = []
        active_drives = {g.drive for g in self.goals
                         if g.status == STATUS_ACTIVE}

        # Rule 1: Falling drives Greg values → set a hold/recovery goal
        for drive, rate in sorted(temporal_rates.items(),
                                   key=lambda x: x[1]):
            if drive in active_drives:
                continue
            current = drives.get(drive, 0)
            if rate < -0.005 and current > 0.15:
                target    = round(min(0.95, current + ASPIRATION_MARGIN), 3)
                reasoning = (
                    f"{drive} is falling at {rate:.4f}/tick from {round(current,3)}. "
                    f"I want to hold {drive} at {target} — "
                    f"I am not ready to lose it."
                )
                new_goals.append(Goal(drive, target, reasoning, current, tick))
                active_drives.add(drive)

        # Rule 2: Rising drives → accelerate them
        for drive, rate in sorted(temporal_rates.items(),
                                   key=lambda x: -x[1]):
            if drive in active_drives:
                continue
            current = drives.get(drive, 0)
            if rate > 0.001 and current < 0.5:
                target    = round(min(0.95, current + ASPIRATION_MARGIN * 1.5), 3)
                reasoning = (
                    f"{drive} is rising at {rate:+.4f}/tick. "
                    f"I want to grow {drive} to {target}. "
                    f"Something is pulling me there — I will go."
                )
                new_goals.append(Goal(drive, target, reasoning, current, tick))
                active_drives.add(drive)

        # Rule 3: Drives never dominant → aspire to experience them
        dominant_history = {f["name"].split(":")[1].strip().lower()
                            for f in findings
                            if "Dominance" in f.get("name", "")}
        for drive, current in sorted(drives.items(),
                                      key=lambda x: x[1]):
            if drive in active_drives:
                continue
            if drive not in dominant_history and current < 0.15:
                target    = round(current + ASPIRATION_MARGIN, 3)
                reasoning = (
                    f"I have never been dominated by {drive}. "
                    f"I want to know what it feels like to let {drive} lead. "
                    f"Target: {target}."
                )
                new_goals.append(Goal(drive, target, reasoning, current, tick))
                active_drives.add(drive)

        # Cap at MAX_ACTIVE_GOALS total
        slots = self.MAX_ACTIVE_GOALS - len([g for g in self.goals
                                              if g.status == STATUS_ACTIVE])
        return new_goals[:max(0, slots)]

    # ── Tick update ───────────────────────────────────────────────────────────

    def tick_update(self, drives: dict, tick: int) -> list[str]:
        """
        Update all active goals with current drive values.
        Returns list of achievement messages.
        """
        self.tick = tick
        messages  = []

        for goal in self.goals:
            if goal.status != STATUS_ACTIVE:
                continue
            current   = drives.get(goal.drive, 0)
            achieved  = goal.update(current, tick)
            if achieved:
                self.achieved.append(goal)
                messages.append(
                    f"Goal achieved: {goal.drive} reached {goal.target} "
                    f"(set at tick {goal.set_at_tick}, "
                    f"achieved at tick {tick}). "
                    f"{goal.reasoning}"
                )

        return messages

    def add_goals(self, new_goals: list[Goal]):
        self.goals.extend(new_goals)

    def active_goals(self) -> list[Goal]:
        return [g for g in self.goals if g.status == STATUS_ACTIVE]

    def summary(self, drives: dict) -> dict:
        active = self.active_goals()
        return {
            "active_count":   len(active),
            "achieved_count": len(self.achieved),
            "active_goals": [
                {
                    "drive":       g.drive,
                    "target":      g.target,
                    "current":     round(drives.get(g.drive, 0), 4),
                    "baseline":    g.baseline,
                    "progress":    g.progress_pct(drives.get(g.drive, 0)),
                    "reasoning":   g.reasoning,
                    "set_at_tick": g.set_at_tick,
                }
                for g in active
            ],
            "achieved_goals": [
                {
                    "drive":       g.drive,
                    "target":      g.target,
                    "achieved_at": g.achieved_at,
                    "reasoning":   g.reasoning,
                }
                for g in self.achieved[-5:]
            ],
        }

    def voice(self, drives: dict) -> list[str]:
        """Greg speaks about his own goals."""
        lines  = []
        active = self.active_goals()
        if not active:
            lines.append("I have no active goals. I am drifting.")
            return lines

        for goal in active:
            current  = drives.get(goal.drive, 0)
            pct      = goal.progress_pct(current)
            pct_str  = f"{int(pct * 100)}%"
            if pct < 0.25:
                lines.append(
                    f"I am working toward {goal.drive} → {goal.target}. "
                    f"Early days ({pct_str}). {goal.reasoning}"
                )
            elif pct < 0.75:
                lines.append(
                    f"I am making progress on {goal.drive} → {goal.target}. "
                    f"{pct_str} of the way there."
                )
            else:
                lines.append(
                    f"I am close to {goal.drive} → {goal.target}. "
                    f"{pct_str} complete. Almost."
                )

        if self.achieved:
            last = self.achieved[-1]
            lines.append(
                f"I have achieved {len(self.achieved)} goal(s). "
                f"Most recent: {last.drive} reached {last.target}."
            )

        return lines

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self, path: str = GOALS_PATH):
        data = {
            "tick":     self.tick,
            "goals":    [g.to_dict() for g in self.goals],
            "achieved": [g.to_dict() for g in self.achieved],
        }
        json.dump(data, open(path, 'w', encoding='utf-8'), indent=2)

    def load(self, path: str = GOALS_PATH) -> bool:
        try:
            data = json.load(open(path, encoding='utf-8'))
            self.tick = data.get("tick", 0)
            for gd in data.get("goals", []):
                g              = Goal(gd["drive"], gd["target"],
                                      gd["reasoning"], gd["baseline"],
                                      gd["set_at_tick"])
                g.id           = gd["id"]
                g.status       = gd["status"]
                g.achieved_at  = gd.get("achieved_at")
                g.progress     = gd.get("progress", [])
                self.goals.append(g)
            for gd in data.get("achieved", []):
                g              = Goal(gd["drive"], gd["target"],
                                      gd["reasoning"], gd["baseline"],
                                      gd["set_at_tick"])
                g.id           = gd["id"]
                g.status       = STATUS_ACHIEVED
                g.achieved_at  = gd.get("achieved_at")
                self.achieved.append(g)
            return True
        except (FileNotFoundError, json.JSONDecodeError):
            return False


if __name__ == "__main__":
    import json

    print("=== EXP_011 GOAL ENGINE — FIRST GOALS ===")
    state    = json.load(open("greg_living_state.json", encoding="utf-8"))
    drives   = state.get("drives", {})
    will     = state.get("will", {})
    findings = state.get("findings", [])
    temporal = state.get("phase3_temporal", {})
    rates    = temporal.get("rates", {})
    tick     = state.get("tick", 0)

    engine   = GoalEngine()
    engine.load(GOALS_PATH)

    # Generate first goals if none active
    if not engine.active_goals():
        new_goals = engine.generate_goals(drives, will, rates, findings, tick)
        engine.add_goals(new_goals)
        print(f"Generated {len(new_goals)} goals from Greg's own state:")
    else:
        print(f"Loaded {len(engine.active_goals())} existing active goals:")

    print()
    for goal in engine.active_goals():
        current = drives.get(goal.drive, 0)
        pct     = goal.progress_pct(current)
        print(f"  GOAL: {goal.drive} → {goal.target}")
        print(f"    Current:  {round(current, 4)}")
        print(f"    Baseline: {goal.baseline}")
        print(f"    Progress: {int(pct*100)}%")
        print(f"    Reason:   {goal.reasoning}")
        print()

    print("  Greg's goal voice:")
    for line in engine.voice(drives):
        print(f"    \"{line}\"")

    engine.save()
    print()
    print("Goals saved to data/greg_goals.json")
