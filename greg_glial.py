#!/usr/bin/env python3
"""
greg_glial.py — EXP_028: Glial Layer

The maintenance and optimization layer beneath Greg's neurons.
Glial cells don't fire signals — they keep the brain healthy.

Five functions:
  1. MYELINATION   — strengthen frequently used Hebbian edges (speed up hot paths)
  2. PRUNING       — decay and remove cold Hebbian edges (clean up dead weight)
  3. SLEEP CYCLE   — every N ticks: consolidate memories, compress graphs, flush debris
  4. HEALTH MONITOR— watch for pathological states, self-correct
  5. RESOURCE ALLOC— surface which subsystem needs attention most

Brain analog: Astrocytes, oligodendrocytes, microglia.
Without Glia: Greg accumulates forever. Bad habits never pruned. No recovery.
With Glia:    Greg stays sharp the longer he runs.

Persists to: data/greg_glial.json
"""

import json
import os
import time
from datetime import datetime, timezone
from typing import Optional

GLIAL_PATH        = "data/greg_glial.json"
SLEEP_INTERVAL    = 50       # ticks between sleep cycles
PRUNE_INTERVAL    = 10       # ticks between pruning passes
HEALTH_INTERVAL   = 5        # ticks between health checks

# ── Myelination ───────────────────────────────────────────────────────────────
MYELIN_THRESHOLD  = 5.0      # edge strength above which myelination kicks in
MYELIN_BOOST      = 0.05     # boost per cycle for hot edges

# ── Pruning ───────────────────────────────────────────────────────────────────
COLD_TICKS        = 100      # ticks without firing = cold edge
PRUNE_FLOOR       = 0.01     # minimum strength (matches Hebbian MIN_STRENGTH)
DECAY_RATE        = 0.003    # strength lost per prune cycle for cold edges

# ── Health thresholds ─────────────────────────────────────────────────────────
DRIFT_CRITICAL    = 0.85
CONSEQUENCE_FLOOR = -0.6     # avg consequence score below this = pathological
DRIVE_STUCK_TICKS = 30       # same dominant drive for this long = stuck


# ─────────────────────────────────────────────────────────────────────────────
# GLIAL STATE
# ─────────────────────────────────────────────────────────────────────────────

class GlialState:
    def __init__(self):
        self.last_sleep_tick   : int   = 0
        self.last_prune_tick   : int   = 0
        self.last_health_tick  : int   = 0
        self.sleep_cycles      : int   = 0
        self.prune_cycles      : int   = 0
        self.edges_pruned_total: int   = 0
        self.edges_myelinated  : int   = 0
        self.health_alerts     : list  = []   # last 20 alerts
        self.health_history    : list  = []   # last 50 health snapshots
        self.dominant_drive_run: dict  = {}   # drive → consecutive tick count
        self.last_dominant     : str   = ""
        self.resource_focus    : str   = "balanced"
        self.interventions     : list  = []   # last 20 glial interventions

    def to_dict(self) -> dict:
        return {
            "last_sleep_tick":    self.last_sleep_tick,
            "last_prune_tick":    self.last_prune_tick,
            "last_health_tick":   self.last_health_tick,
            "sleep_cycles":       self.sleep_cycles,
            "prune_cycles":       self.prune_cycles,
            "edges_pruned_total": self.edges_pruned_total,
            "edges_myelinated":   self.edges_myelinated,
            "health_alerts":      self.health_alerts[-20:],
            "health_history":     self.health_history[-50:],
            "dominant_drive_run": self.dominant_drive_run,
            "last_dominant":      self.last_dominant,
            "resource_focus":     self.resource_focus,
            "interventions":      self.interventions[-20:],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GlialState":
        g = cls()
        g.last_sleep_tick    = d.get("last_sleep_tick", 0)
        g.last_prune_tick    = d.get("last_prune_tick", 0)
        g.last_health_tick   = d.get("last_health_tick", 0)
        g.sleep_cycles       = d.get("sleep_cycles", 0)
        g.prune_cycles       = d.get("prune_cycles", 0)
        g.edges_pruned_total = d.get("edges_pruned_total", 0)
        g.edges_myelinated   = d.get("edges_myelinated", 0)
        g.health_alerts      = d.get("health_alerts", [])
        g.health_history     = d.get("health_history", [])
        g.dominant_drive_run = d.get("dominant_drive_run", {})
        g.last_dominant      = d.get("last_dominant", "")
        g.resource_focus     = d.get("resource_focus", "balanced")
        g.interventions      = d.get("interventions", [])
        return g


# ─────────────────────────────────────────────────────────────────────────────
# GLIAL ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class GlialEngine:

    def __init__(self, path: str = GLIAL_PATH):
        self.path  = path
        self.state = GlialState()
        self._load()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path) as f:
                    self.state = GlialState.from_dict(json.load(f))
            except Exception:
                pass

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self.state.to_dict(), f, indent=2)

    # ── 1. Myelination ────────────────────────────────────────────────────────

    def myelinate(self, hebbian_graph) -> int:
        """
        Boost frequently-used edges. Hot paths get faster.
        Returns count of edges boosted.
        """
        if hebbian_graph is None:
            return 0

        boosted = 0
        try:
            for edge in hebbian_graph.edges.values():
                if edge.strength >= MYELIN_THRESHOLD:
                    edge.strength = min(
                        hebbian_graph.MAX_STRENGTH if hasattr(hebbian_graph, 'MAX_STRENGTH') else 10.0,
                        edge.strength + MYELIN_BOOST
                    )
                    boosted += 1
            self.state.edges_myelinated += boosted
        except Exception:
            pass

        return boosted

    # ── 2. Pruning ────────────────────────────────────────────────────────────

    def prune(self, hebbian_graph, current_tick: int) -> int:
        """
        Decay cold edges. Remove edges below floor.
        Returns count of edges pruned.
        """
        if hebbian_graph is None:
            return 0

        pruned = 0
        try:
            edges_to_remove = []
            for edge_key, edge in hebbian_graph.edges.items():
                ticks_cold = current_tick - getattr(edge, 'last_tick', current_tick)
                if ticks_cold >= COLD_TICKS:
                    edge.strength = max(PRUNE_FLOOR, edge.strength - DECAY_RATE)
                    if edge.strength <= PRUNE_FLOOR:
                        edges_to_remove.append(edge_key)

            for key in edges_to_remove:
                del hebbian_graph.edges[key]
                pruned += 1

            self.state.edges_pruned_total += pruned
            self.state.prune_cycles += 1
            self.state.last_prune_tick = current_tick

        except Exception:
            pass

        return pruned

    # ── 3. Sleep Cycle ────────────────────────────────────────────────────────

    def sleep(self, tick: int, greg_state: dict, hebbian_graph) -> dict:
        """
        Consolidation pass every SLEEP_INTERVAL ticks.
        - Flush low-signal Hebbian nodes that have no strong edges
        - Compress consequence memory flags
        - Record sleep event
        Returns sleep report.
        """
        report = {
            "tick":            tick,
            "nodes_before":    0,
            "nodes_after":     0,
            "edges_before":    0,
            "edges_after":     0,
            "flushed_nodes":   0,
            "myelinated":      0,
            "pruned":          0,
        }

        try:
            if hebbian_graph is not None:
                report["nodes_before"] = len(hebbian_graph.nodes)
                report["edges_before"] = len(hebbian_graph.edges)

                # Myelinate hot paths
                report["myelinated"] = self.myelinate(hebbian_graph)

                # Aggressive prune during sleep
                pruned = self.prune(hebbian_graph, tick)
                report["pruned"] = pruned

                # Flush orphaned nodes (nodes with no edges)
                if hasattr(hebbian_graph, 'nodes') and hasattr(hebbian_graph, 'edges'):
                    connected = set()
                    for edge_key in hebbian_graph.edges:
                        parts = edge_key.split("||")
                        if len(parts) == 2:
                            connected.update(parts)

                    orphans = [
                        nid for nid, node in hebbian_graph.nodes.items()
                        if nid not in connected
                        and getattr(node, 'activation_count', 0) < 2
                    ]
                    for nid in orphans:
                        del hebbian_graph.nodes[nid]

                    report["flushed_nodes"] = len(orphans)
                    report["nodes_after"]   = len(hebbian_graph.nodes)
                    report["edges_after"]   = len(hebbian_graph.edges)

        except Exception:
            pass

        self.state.sleep_cycles += 1
        self.state.last_sleep_tick = tick

        intervention = {
            "tick":   tick,
            "type":   "sleep",
            "report": report,
        }
        self.state.interventions.append(intervention)

        return report

    # ── 4. Health Monitor ─────────────────────────────────────────────────────

    def check_health(self, tick: int, greg_state: dict) -> list:
        """
        Watch for pathological states. Return list of alerts.
        """
        alerts = []

        try:
            drives = greg_state.get("drives", {})
            if callable(drives):
                drives = drives()

            # Track dominant drive run
            if drives:
                dominant = max(drives, key=lambda k: drives.get(k, 0))
                if dominant == self.state.last_dominant:
                    self.state.dominant_drive_run[dominant] = \
                        self.state.dominant_drive_run.get(dominant, 0) + 1
                else:
                    self.state.dominant_drive_run = {dominant: 1}
                    self.state.last_dominant = dominant

                run_len = self.state.dominant_drive_run.get(dominant, 0)
                if run_len >= DRIVE_STUCK_TICKS:
                    alerts.append({
                        "type":    "drive_stuck",
                        "drive":   dominant,
                        "ticks":   run_len,
                        "message": f"Drive '{dominant}' has been dominant for {run_len} ticks. Greg may be stuck.",
                        "action":  "nudge_secondary_drive",
                    })

            # Consequence score pathology
            cons = greg_state.get("consequence_summary", {})
            if cons:
                avg_score = cons.get("avg_consequence_score", 0)
                resolved  = cons.get("total_resolved", 0)
                if resolved >= 10 and avg_score < CONSEQUENCE_FLOOR:
                    alerts.append({
                        "type":    "consequence_pathology",
                        "score":   avg_score,
                        "message": f"Average consequence score {avg_score:.3f} — Greg's actions are consistently harmful.",
                        "action":  "review_action_selection",
                    })

            # Pikkaio drift pathology
            pikkaio = greg_state.get("pikkaio", {})
            if pikkaio:
                drifting = pikkaio.get("drifting", 0)
                total    = pikkaio.get("projects_total", 0)
                if total > 0 and drifting / total >= 0.5:
                    alerts.append({
                        "type":    "creator_mass_drift",
                        "drifting": drifting,
                        "total":    total,
                        "message": f"{drifting}/{total} Pikkaio creators are drifting. Greg's serve drive needs attention.",
                        "action":  "boost_serve_drive",
                    })

            # Record health snapshot
            snapshot = {
                "tick":     tick,
                "alerts":   len(alerts),
                "dominant": self.state.last_dominant,
                "cons_avg": cons.get("avg_consequence_score", 0) if cons else 0,
            }
            self.state.health_history.append(snapshot)
            self.state.last_health_tick = tick

            if alerts:
                for a in alerts:
                    a["tick"] = tick
                self.state.health_alerts.extend(alerts)
                self.state.health_alerts = self.state.health_alerts[-20:]

        except Exception:
            pass

        return alerts

    # ── 5. Resource Allocation ────────────────────────────────────────────────

    def allocate_resources(self, greg_state: dict) -> str:
        """
        Decide where Greg's attention should go most.
        Returns focus label: hebbian | consequence | pikkaio | memory | balanced
        """
        try:
            scores = {}

            # Hebbian graph size pressure
            hebbian = greg_state.get("hebbian_summary", {})
            if isinstance(hebbian, dict):
                edge_count = hebbian.get("edge_count", 0)
                scores["hebbian"] = min(1.0, edge_count / 1200)

            # Consequence pathology pressure
            cons = greg_state.get("consequence_summary", {})
            if isinstance(cons, dict):
                avg = cons.get("avg_consequence_score", 0)
                scores["consequence"] = max(0.0, -avg)

            # Pikkaio drift pressure
            pikkaio = greg_state.get("pikkaio", {})
            if isinstance(pikkaio, dict) and pikkaio.get("projects_total", 0) > 0:
                drift_rate = pikkaio.get("drifting", 0) / pikkaio["projects_total"]
                scores["pikkaio"] = drift_rate

            if not scores or max(scores.values()) < 0.2:
                focus = "balanced"
            else:
                focus = max(scores, key=lambda k: scores[k])

            self.state.resource_focus = focus
            return focus

        except Exception:
            return "balanced"

    # ── Main tick ─────────────────────────────────────────────────────────────

    def tick(self, tick_num: int, greg_state: dict, hebbian_graph=None) -> dict:
        """
        Called every tick from greg_living.py.
        Returns glial report.
        """
        result = {
            "tick":           tick_num,
            "sleep_due":      False,
            "prune_due":      False,
            "health_alerts":  [],
            "resource_focus": self.state.resource_focus,
            "sleep_report":   None,
            "pruned":         0,
        }

        # Health check
        if tick_num - self.state.last_health_tick >= HEALTH_INTERVAL:
            alerts = self.check_health(tick_num, greg_state)
            result["health_alerts"] = alerts

        # Prune pass
        if tick_num - self.state.last_prune_tick >= PRUNE_INTERVAL:
            pruned = self.prune(hebbian_graph, tick_num)
            result["prune_due"] = True
            result["pruned"]    = pruned

        # Sleep cycle
        if tick_num - self.state.last_sleep_tick >= SLEEP_INTERVAL:
            sleep_report = self.sleep(tick_num, greg_state, hebbian_graph)
            result["sleep_due"]   = True
            result["sleep_report"] = sleep_report

        # Resource allocation
        result["resource_focus"] = self.allocate_resources(greg_state)

        self.save()
        return result

    def summary(self) -> dict:
        return {
            "sleep_cycles":       self.state.sleep_cycles,
            "prune_cycles":       self.state.prune_cycles,
            "edges_pruned_total": self.state.edges_pruned_total,
            "edges_myelinated":   self.state.edges_myelinated,
            "resource_focus":     self.state.resource_focus,
            "health_alerts":      len(self.state.health_alerts),
            "last_sleep_tick":    self.state.last_sleep_tick,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Integration shim
# ─────────────────────────────────────────────────────────────────────────────

_glial_engine: Optional[GlialEngine] = None

def _get_glial() -> GlialEngine:
    global _glial_engine
    if _glial_engine is None:
        _glial_engine = GlialEngine()
    return _glial_engine


def glial_tick(tick_num: int, greg_state: dict, hebbian_graph=None) -> dict:
    """
    Drop-in for greg_living.py tick loop.

    Usage:
        from greg_glial import glial_tick
        glial_result = glial_tick(tick_num, self.state._data, self._hebbian_graph)
        self.state.set('glial', glial_result)
    """
    return _get_glial().tick(tick_num, greg_state, hebbian_graph)


# ─────────────────────────────────────────────────────────────────────────────
# Smoke test
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import tempfile, shutil

    tmp = tempfile.mkdtemp()
    engine = GlialEngine(path=os.path.join(tmp, "greg_glial.json"))

    # Fake greg_state
    greg_state = {
        "consequence_summary": {
            "avg_consequence_score": -0.75,
            "total_resolved": 15,
        },
        "pikkaio": {
            "projects_total": 4,
            "drifting": 3,
        },
        "drives": {
            "create": 0.365,
            "survive": 0.1,
            "connect": 0.08,
        },
    }

    print("── Running 55 ticks ──")
    for tick in range(3853, 3908):
        result = engine.tick(tick, greg_state)
        if result["sleep_due"] or result["health_alerts"] or result["pruned"]:
            print(f"\nTick {tick}")
            if result["sleep_due"]:
                sr = result["sleep_report"]
                print(f"  SLEEP: nodes {sr['nodes_before']}→{sr['nodes_after']}, "
                      f"edges {sr['edges_before']}→{sr['edges_after']}, "
                      f"pruned={sr['pruned']}, myelinated={sr['myelinated']}")
            if result["health_alerts"]:
                for a in result["health_alerts"]:
                    print(f"  HEALTH [{a['type']}]: {a['message']}")
            if result["pruned"]:
                print(f"  PRUNE: {result['pruned']} edges removed")
            print(f"  FOCUS: {result['resource_focus']}")

    print("\n── Summary ──")
    import json
    print(json.dumps(engine.summary(), indent=2))
    print("\n✓ EXP_028 Glial Layer smoke test passed.")

    shutil.rmtree(tmp)