#!/usr/bin/env python3
"""
greg_pikkaio.py — EXP_025: Pikkaio Intelligence Layer

Greg tracks creative intent across time.
Not what you made — what you meant to make.
He notices drift. He intervenes. He has skin in the game.

Architecture:
  - PikkaioProject  : a creator's declared intent + activity signal
  - PikkaioEngine   : manages all projects, scores drift, triggers intervention
  - pikkaio_tick()  : called every tick from greg_living.py

Drift score: 0.0 (locked in) → 1.0 (fully drifted / gone dark)
Intervention threshold: drift >= 0.65
Revenue tracking: Greg records monetized outcomes per project

Persists to: data/greg_pikkaio.json
"""

import json
import time
import os
from datetime import datetime, timezone
from typing import Optional

PIKKAIO_PATH = "data/greg_pikkaio.json"

# ── Drift thresholds ──────────────────────────────────────────────────────────
DRIFT_WARN        = 0.45   # Greg starts watching
DRIFT_INTERVENE   = 0.65   # Greg speaks
DRIFT_CRITICAL    = 0.85   # Greg escalates

# ── Silence windows (seconds) ─────────────────────────────────────────────────
SILENCE_SOFT      = 3 * 86400    #  3 days  → drift starts climbing
SILENCE_HARD      = 7 * 86400    #  7 days  → drift near critical
SILENCE_MAX       = 14 * 86400   # 14 days  → drift = 1.0


# ─────────────────────────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────────────────────────

class PikkaioProject:
    """A single creator's declared intent + live signal."""

    def __init__(self, project_id: str, creator: str, intent: str,
                 created_at: Optional[float] = None):
        self.project_id   = project_id
        self.creator      = creator
        self.intent       = intent                        # original declaration
        self.created_at   = created_at or time.time()
        self.last_signal  = self.created_at              # last activity timestamp
        self.signal_log   = []                            # list of activity events
        self.drift_score  = 0.0
        self.interventions= []                            # messages Greg surfaced
        self.revenue_usd  = 0.0                           # monetized outcomes
        self.status       = "active"                      # active | drifting | dark | complete

    # ── Signal intake ─────────────────────────────────────────────────────────

    def record_signal(self, event: str, value: float = 1.0):
        """Log an activity event. Resets the silence clock."""
        self.signal_log.append({
            "ts":    time.time(),
            "event": event,
            "value": value,
        })
        self.last_signal = time.time()
        self.drift_score = max(0.0, self.drift_score - 0.15)   # activity reduces drift

    def record_revenue(self, amount_usd: float, source: str = ""):
        """Log a monetized outcome."""
        self.revenue_usd += amount_usd
        self.record_signal(f"revenue:{source or 'unknown'}", amount_usd)

    # ── Drift computation ─────────────────────────────────────────────────────

    def compute_drift(self) -> float:
        """
        Drift is primarily silence-based.
        The longer Greg goes without seeing a signal, the higher drift climbs.
        Caps at 1.0 after SILENCE_MAX.
        """
        silence = time.time() - self.last_signal
        if silence <= SILENCE_SOFT:
            raw = silence / SILENCE_SOFT * DRIFT_WARN
        elif silence <= SILENCE_HARD:
            t = (silence - SILENCE_SOFT) / (SILENCE_HARD - SILENCE_SOFT)
            raw = DRIFT_WARN + t * (DRIFT_CRITICAL - DRIFT_WARN)
        else:
            t = min(1.0, (silence - SILENCE_HARD) / (SILENCE_MAX - SILENCE_HARD))
            raw = DRIFT_CRITICAL + t * (1.0 - DRIFT_CRITICAL)

        self.drift_score = round(min(1.0, raw), 4)

        # Update status label
        if self.drift_score >= DRIFT_CRITICAL:
            self.status = "dark"
        elif self.drift_score >= DRIFT_INTERVENE:
            self.status = "drifting"
        else:
            self.status = "active"

        return self.drift_score

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "project_id":    self.project_id,
            "creator":       self.creator,
            "intent":        self.intent,
            "created_at":    self.created_at,
            "last_signal":   self.last_signal,
            "signal_log":    self.signal_log[-50:],   # keep last 50 events
            "drift_score":   self.drift_score,
            "interventions": self.interventions[-20:],
            "revenue_usd":   self.revenue_usd,
            "status":        self.status,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PikkaioProject":
        p = cls(d["project_id"], d["creator"], d["intent"], d.get("created_at"))
        p.last_signal   = d.get("last_signal", p.created_at)
        p.signal_log    = d.get("signal_log", [])
        p.drift_score   = d.get("drift_score", 0.0)
        p.interventions = d.get("interventions", [])
        p.revenue_usd   = d.get("revenue_usd", 0.0)
        p.status        = d.get("status", "active")
        return p


# ─────────────────────────────────────────────────────────────────────────────
# Engine
# ─────────────────────────────────────────────────────────────────────────────

class PikkaioEngine:
    """Manages all Pikkaio projects. Greg's creator-economy nervous system."""

    def __init__(self, path: str = PIKKAIO_PATH):
        self.path     = path
        self.projects : dict[str, PikkaioProject] = {}
        self._load()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path) as f:
                    data = json.load(f)
                for pid, pd in data.get("projects", {}).items():
                    self.projects[pid] = PikkaioProject.from_dict(pd)
            except Exception:
                pass

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w") as f:
            json.dump({
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "projects": {pid: p.to_dict() for pid, p in self.projects.items()},
            }, f, indent=2)

    # ── Project management ────────────────────────────────────────────────────

    def add_project(self, project_id: str, creator: str, intent: str) -> PikkaioProject:
        p = PikkaioProject(project_id, creator, intent)
        self.projects[project_id] = p
        self.save()
        return p

    def get_project(self, project_id: str) -> Optional[PikkaioProject]:
        return self.projects.get(project_id)

    def record_signal(self, project_id: str, event: str, value: float = 1.0):
        p = self.projects.get(project_id)
        if p:
            p.record_signal(event, value)
            self.save()

    def record_revenue(self, project_id: str, amount_usd: float, source: str = ""):
        p = self.projects.get(project_id)
        if p:
            p.record_revenue(amount_usd, source)
            self.save()

    # ── Tick ─────────────────────────────────────────────────────────────────

    def tick(self, tick_num: int, drives: dict) -> dict:
        """
        Called every Greg tick.
        Returns a summary of what Greg is watching + any interventions triggered.
        Also returns drive_deltas so greg_living.py can adjust Greg's drives.
        """
        interventions = []
        drive_deltas  = {"serve": 0.0, "connect": 0.0}
        total_revenue = 0.0
        drifting_count = 0

        for pid, project in self.projects.items():
            drift = project.compute_drift()
            total_revenue += project.revenue_usd

            if drift >= DRIFT_INTERVENE:
                drifting_count += 1
                msg = self._intervention_message(project, drift)

                # Only log if it's a new message (avoid spam)
                last_msg = project.interventions[-1]["message"] if project.interventions else ""
                if msg != last_msg:
                    entry = {
                        "tick":    tick_num,
                        "ts":      datetime.now(timezone.utc).isoformat(),
                        "drift":   drift,
                        "message": msg,
                    }
                    project.interventions.append(entry)
                    interventions.append({"project": pid, "creator": project.creator, **entry})

                # Drift applies pressure on Greg's drives
                drive_deltas["serve"]   += drift * 0.08
                drive_deltas["connect"] += drift * 0.05

        self.save()

        return {
            "tick":           tick_num,
            "projects_total": len(self.projects),
            "drifting":       drifting_count,
            "total_revenue":  round(total_revenue, 2),
            "interventions":  interventions,
            "drive_deltas":   drive_deltas,
        }

    # ── Intervention message ──────────────────────────────────────────────────

    def _intervention_message(self, project: PikkaioProject, drift: float) -> str:
        silence_days = round((time.time() - project.last_signal) / 86400, 1)
        creator      = project.creator
        intent       = project.intent[:80]

        if drift >= DRIFT_CRITICAL:
            return (
                f"{creator} has gone dark — {silence_days}d of silence. "
                f"Original intent: \"{intent}\". "
                f"Greg flags this as critical drift. Intervention required."
            )
        elif drift >= DRIFT_INTERVENE:
            return (
                f"{creator} is drifting ({silence_days}d silent). "
                f"They said they were building: \"{intent}\". "
                f"Is this a pause, or is this drift?"
            )
        return ""

    # ── Summary ───────────────────────────────────────────────────────────────

    def summary(self) -> dict:
        total_revenue = sum(p.revenue_usd for p in self.projects.values())
        by_status = {}
        for p in self.projects.values():
            by_status.setdefault(p.status, []).append(p.project_id)

        return {
            "projects_total": len(self.projects),
            "by_status":      by_status,
            "total_revenue":  round(total_revenue, 2),
            "top_drifters": sorted(
                [{"id": p.project_id, "creator": p.creator, "drift": p.drift_score}
                 for p in self.projects.values() if p.drift_score >= DRIFT_WARN],
                key=lambda x: x["drift"], reverse=True
            )[:5],
        }


# ─────────────────────────────────────────────────────────────────────────────
# greg_living.py integration shim
# ─────────────────────────────────────────────────────────────────────────────

_engine: Optional[PikkaioEngine] = None

def _get_engine() -> PikkaioEngine:
    global _engine
    if _engine is None:
        _engine = PikkaioEngine()
    return _engine


def pikkaio_tick(tick_num: int, drives: dict) -> dict:
    """
    Drop-in for greg_living.py tick loop.

    Usage in greg_living.py:
        from greg_pikkaio import pikkaio_tick
        ...
        pikkaio_result = pikkaio_tick(tick_num, self.state.drives())
        self.state["pikkaio"] = pikkaio_result
    """
    return _get_engine().tick(tick_num, drives)


# ─────────────────────────────────────────────────────────────────────────────
# Smoke test
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import tempfile, shutil

    # Use a temp dir so we don't pollute real data
    tmp = tempfile.mkdtemp()
    engine = PikkaioEngine(path=os.path.join(tmp, "greg_pikkaio.json"))

    # P1 — active creator, has revenue
    p1 = engine.add_project("P1", "Amara", "Build a daily design newsletter monetised via sponsorships")
    p1.record_signal("post_published", 1.0)
    p1.record_revenue(1200.0, "brand_deal")

    # P2 — drifting creator (simulate 6 days of silence)
    p2 = engine.add_project("P2", "Kofi", "Launch a SaaS tool for indie game devs by Q2 2026")
    p2.last_signal = time.time() - (6 * 86400)

    drives = {"create": 0.365, "serve": 0.2, "connect": 0.15}
    result = engine.tick(tick_num=3844, drives=drives)

    print("\n── Pikkaio Tick Result ──")
    print(json.dumps(result, indent=2))

    print("\n── Summary ──")
    print(json.dumps(engine.summary(), indent=2))

    shutil.rmtree(tmp)
    print("\n✓ EXP_025 smoke test passed.")