"""
EXP_021 — Hebbian Knowledge Graph
"Neurons that fire together, wire together."

How it works:
  Every tick, Greg takes an action in a location.
  The edge between that action and that location gets stronger.
  Edges that never fire together decay slowly.
  High surprise (from EXP_020) amplifies strengthening — surprise = important.
  Over time, Greg builds a map of what tends to happen where,
  and what actions cluster with what drives.

Architecture:
  Nodes  — actions, locations, drives, concepts
  Edges  — co-activation count + strength (0.0–10.0)
  Hebbian rule: Δstrength = α * surprise_amplifier * co_activation
  Decay rule:   Δstrength = -β * (1 / (1 + count))  per tick without fire

No backprop. No gradient descent. Pure Hebbian learning.
This is EXP_008 (KnowledgeGraph) evolved — same graph topology,
but edges now carry learned weights from co-activation history.
"""

import json
import os
import math
from datetime import datetime, timezone
from collections import defaultdict
from typing import Optional

HEBBIAN_PATH = "data/greg_hebbian.json"

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────

ALPHA        = 0.08    # base learning rate (strengthening)
BETA         = 0.002   # base decay rate (forgetting)
MAX_STRENGTH = 10.0    # edge strength ceiling
MIN_STRENGTH = 0.01    # edge strength floor — below this, prune
SURPRISE_AMP = {       # surprise level → amplification multiplier
    "NONE":     1.0,
    "LOW":      1.3,
    "MODERATE": 1.8,
    "HIGH":     2.5,
    "SHOCK":    4.0,
}
MAX_NODES = 300
MAX_EDGES = 1200


# ─────────────────────────────────────────────
# GRAPH STRUCTURES
# ─────────────────────────────────────────────

class HebbianNode:
    __slots__ = ("id", "ntype", "activation_count", "last_tick", "weight")

    def __init__(self, node_id: str, ntype: str):
        self.id               = node_id
        self.ntype            = ntype       # "action" | "location" | "drive" | "concept"
        self.activation_count = 0
        self.last_tick        = 0
        self.weight           = 1.0         # importance — rises with activations

    def activate(self, tick: int):
        self.activation_count += 1
        self.last_tick         = tick
        self.weight            = min(10.0, self.weight + 0.02)

    def to_dict(self) -> dict:
        return {
            "id":               self.id,
            "ntype":            self.ntype,
            "activation_count": self.activation_count,
            "last_tick":        self.last_tick,
            "weight":           round(self.weight, 4),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "HebbianNode":
        n                   = cls(d["id"], d["ntype"])
        n.activation_count  = d.get("activation_count", 0)
        n.last_tick         = d.get("last_tick", 0)
        n.weight            = d.get("weight", 1.0)
        return n


class HebbianEdge:
    __slots__ = ("source", "target", "strength", "co_activations",
                 "last_fired", "created_tick")

    def __init__(self, source: str, target: str, tick: int = 0):
        self.source        = source
        self.target        = target
        self.strength      = 1.0
        self.co_activations = 1
        self.last_fired    = tick
        self.created_tick  = tick

    def fire(self, tick: int, amplifier: float = 1.0):
        """Hebbian strengthening — nodes that co-activate together wire together."""
        delta           = ALPHA * amplifier
        self.strength   = min(MAX_STRENGTH, self.strength + delta)
        self.co_activations += 1
        self.last_fired = tick

    def decay(self, current_tick: int):
        """Edges that don't fire together fade together."""
        ticks_idle    = max(0, current_tick - self.last_fired)
        decay_amount  = BETA * math.log1p(ticks_idle) / (1 + self.co_activations * 0.1)
        self.strength = max(MIN_STRENGTH, self.strength - decay_amount)

    def to_dict(self) -> dict:
        return {
            "source":         self.source,
            "target":         self.target,
            "strength":       round(self.strength, 4),
            "co_activations": self.co_activations,
            "last_fired":     self.last_fired,
            "created_tick":   self.created_tick,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "HebbianEdge":
        e                  = cls(d["source"], d["target"], d.get("created_tick", 0))
        e.strength         = d.get("strength", 1.0)
        e.co_activations   = d.get("co_activations", 1)
        e.last_fired       = d.get("last_fired", 0)
        return e


# ─────────────────────────────────────────────
# HEBBIAN GRAPH
# ─────────────────────────────────────────────

class HebbianGraph:
    """
    Greg's learned association map.
    Built entirely from co-activation — no external knowledge injection.

    After N ticks, Greg will have learned:
    - Which actions tend to happen at which locations
    - Which drives tend to accompany which actions
    - Which action/drive combos are surprising (and therefore important)
    - The "texture" of his own behaviour as a weighted graph
    """

    def __init__(self):
        self.nodes: dict[str, HebbianNode] = {}
        self.edges: dict[tuple, HebbianEdge] = {}   # (source, target) → edge
        self.tick  = 0
        self.total_fires = 0

    # ── Node management ──────────────────────────────────────────────────────

    def _get_or_create_node(self, node_id: str, ntype: str) -> HebbianNode:
        if node_id not in self.nodes:
            if len(self.nodes) >= MAX_NODES:
                self._prune_nodes()
            self.nodes[node_id] = HebbianNode(node_id, ntype)
        return self.nodes[node_id]

    def _prune_nodes(self):
        """Remove lowest-weight non-concept nodes."""
        candidates = [
            (n.weight, nid)
            for nid, n in self.nodes.items()
            if n.ntype not in ("concept", "drive")
        ]
        candidates.sort()
        for _, nid in candidates[:30]:
            # Also remove edges connected to this node
            dead_keys = [k for k in self.edges if k[0] == nid or k[1] == nid]
            for k in dead_keys:
                del self.edges[k]
            del self.nodes[nid]

    def _prune_edges(self):
        """Remove weakest edges."""
        if len(self.edges) <= MAX_EDGES:
            return
        sorted_edges = sorted(self.edges.items(), key=lambda x: x[1].strength)
        to_remove    = sorted_edges[:len(self.edges) - MAX_EDGES + 100]
        for key, _ in to_remove:
            del self.edges[key]

    # ── Core Hebbian operation ────────────────────────────────────────────────

    def co_activate(self, node_a: str, type_a: str,
                    node_b: str, type_b: str,
                    tick: int, amplifier: float = 1.0):
        """
        Fire both nodes and strengthen their edge.
        This is the core Hebbian operation.
        """
        na = self._get_or_create_node(node_a, type_a)
        nb = self._get_or_create_node(node_b, type_b)
        na.activate(tick)
        nb.activate(tick)

        key = (node_a, node_b)
        if key not in self.edges:
            if len(self.edges) >= MAX_EDGES:
                self._prune_edges()
            self.edges[key] = HebbianEdge(node_a, node_b, tick)
        else:
            self.edges[key].fire(tick, amplifier)

        self.total_fires += 1

    def decay_all(self, current_tick: int):
        """
        Decay all edges that didn't fire this tick.
        Called once per tick after all co-activations.
        """
        dead_keys = []
        for key, edge in self.edges.items():
            if edge.last_fired < current_tick:
                edge.decay(current_tick)
                if edge.strength <= MIN_STRENGTH:
                    dead_keys.append(key)
        for k in dead_keys:
            del self.edges[k]

    # ── Tick interface ────────────────────────────────────────────────────────

    def observe(self, action: str, location: str, drives: dict,
                tick: int, surprise_level: str = "NONE"):
        """
        Called once per tick from greg_living.py.
        Co-activates:
          action ↔ location
          action ↔ dominant_drive
          location ↔ dominant_drive
          action ↔ top_3_drives (weaker)
        Surprise amplifies all edges formed this tick.
        """
        self.tick    = tick
        amplifier    = SURPRISE_AMP.get(surprise_level, 1.0)

        # Dominant drive
        dominant = max(drives, key=drives.get) if drives else "explore"

        # Primary co-activations (full amplification)
        self.co_activate(action,   "action",   location,  "location", tick, amplifier)
        self.co_activate(action,   "action",   dominant,  "drive",    tick, amplifier)
        self.co_activate(location, "location", dominant,  "drive",    tick, amplifier)

        # Secondary co-activations — top 3 drives (half amplification)
        sorted_drives = sorted(drives.items(), key=lambda x: -x[1])
        for drive, val in sorted_drives[:3]:
            if drive != dominant:
                self.co_activate(action, "action", drive, "drive", tick, amplifier * 0.5)

        # Decay everything that didn't fire
        self.decay_all(tick)

    # ── Query ─────────────────────────────────────────────────────────────────

    def strongest_associations(self, node_id: str, n: int = 5) -> list[dict]:
        """Return the N strongest edges from a given node."""
        connected = [
            (edge.strength, edge.target, edge.co_activations)
            for (src, _), edge in self.edges.items()
            if src == node_id
        ]
        connected += [
            (edge.strength, edge.source, edge.co_activations)
            for (_, tgt), edge in self.edges.items()
            if tgt == node_id
        ]
        connected.sort(reverse=True)
        return [
            {"node": n, "strength": round(s, 3), "co_activations": c}
            for s, n, c in connected[:n]
        ]

    def what_follows(self, action: str, n: int = 3) -> list[dict]:
        """What locations and drives co-activate most with this action?"""
        return self.strongest_associations(action, n)

    def where_does(self, drive: str, n: int = 3) -> list[dict]:
        """Which actions and locations co-activate most with this drive?"""
        return self.strongest_associations(drive, n)

    def top_edges(self, n: int = 10) -> list[dict]:
        """Return the N strongest edges in the whole graph."""
        ranked = sorted(self.edges.values(), key=lambda e: -e.strength)
        return [
            {
                "source":         e.source,
                "target":         e.target,
                "strength":       round(e.strength, 3),
                "co_activations": e.co_activations,
            }
            for e in ranked[:n]
        ]

    def summary(self) -> dict:
        """Greg's self-knowledge about his own association map."""
        if not self.edges:
            return {
                "status":      "no associations formed yet",
                "total_nodes": 0,
                "total_edges": 0,
            }

        total_strength  = sum(e.strength for e in self.edges.values())
        avg_strength    = total_strength / len(self.edges)
        strongest_edges = self.top_edges(5)
        node_types      = defaultdict(int)
        for n in self.nodes.values():
            node_types[n.ntype] += 1

        # Most activated nodes
        top_nodes = sorted(self.nodes.values(), key=lambda n: -n.activation_count)[:5]

        return {
            "total_nodes":    len(self.nodes),
            "total_edges":    len(self.edges),
            "total_fires":    self.total_fires,
            "avg_strength":   round(avg_strength, 3),
            "node_types":     dict(node_types),
            "strongest_edges": strongest_edges,
            "most_activated": [
                {"id": n.id, "type": n.ntype, "activations": n.activation_count}
                for n in top_nodes
            ],
        }

    def speak(self) -> str:
        """Greg narrates what he has learned from co-activation."""
        s = self.summary()
        if s.get("status") == "no associations formed yet":
            return "My association map is empty. I have not yet learned what fires with what."

        edges = s.get("strongest_edges", [])
        top   = edges[0] if edges else None

        lines = [
            f"I have {s['total_nodes']} nodes and {s['total_edges']} associations "
            f"built from {s['total_fires']} co-activations."
        ]

        if top:
            lines.append(
                f"My strongest learned association: {top['source']} ↔ {top['target']} "
                f"(strength {top['strength']}, fired {top['co_activations']}x)."
            )

        # What does the dominant action wire to?
        action_nodes = [n for n in self.nodes.values() if n.ntype == "action"]
        if action_nodes:
            top_action = max(action_nodes, key=lambda n: n.activation_count)
            assoc = self.strongest_associations(top_action.id, 3)
            if assoc:
                assoc_str = ", ".join(a["node"] for a in assoc)
                lines.append(
                    f"My most frequent action is '{top_action.id}', "
                    f"which I associate most with: {assoc_str}."
                )

        return " ".join(lines)

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self, path: str = HEBBIAN_PATH):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = {
            "tick":        self.tick,
            "total_fires": self.total_fires,
            "nodes":       {nid: n.to_dict() for nid, n in self.nodes.items()},
            "edges":       [e.to_dict() for e in self.edges.values()],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: str = HEBBIAN_PATH) -> "HebbianGraph":
        g = cls()
        if not os.path.exists(path):
            return g
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            g.tick        = data.get("tick", 0)
            g.total_fires = data.get("total_fires", 0)
            for nid, nd in data.get("nodes", {}).items():
                g.nodes[nid] = HebbianNode.from_dict(nd)
            for ed in data.get("edges", []):
                edge               = HebbianEdge.from_dict(ed)
                g.edges[(edge.source, edge.target)] = edge
        except (json.JSONDecodeError, KeyError):
            pass
        return g


# ─────────────────────────────────────────────
# INTEGRATION HELPER — called from greg_living.py
# ─────────────────────────────────────────────

def hebbian_tick(
    graph: HebbianGraph,
    action: str,
    location: str,
    drives: dict,
    tick: int,
    surprise_level: str = "NONE",
):
    """
    Single tick integration point.
    Call this from greg_living.py EXP_021 block.
    """
    graph.observe(action, location, drives, tick, surprise_level)


# ─────────────────────────────────────────────
# DEMO
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("EXP_021 — Hebbian Knowledge Graph — DEMO")
    print("=" * 60)

    g = HebbianGraph()

    # Simulate 50 ticks of Greg's behaviour
    import random
    actions   = ["build", "learn", "explore", "reflect", "trade", "accumulate"]
    locations = ["spawn", "market", "library", "workshop", "frontier"]
    drives    = {
        "create": 0.37, "reason": 0.28, "connect": 0.22,
        "explore": 0.18, "accumulate": 0.10, "protect": 0.05,
    }
    surprise_levels = ["NONE", "NONE", "NONE", "LOW", "LOW",
                       "MODERATE", "HIGH", "NONE", "NONE", "NONE"]

    print("\nSimulating 50 ticks...")
    for tick in range(1, 51):
        action   = random.choice(actions)
        location = random.choice(locations)
        surprise = random.choice(surprise_levels)

        # Vary drives slightly each tick
        for d in drives:
            drives[d] = max(0.0, min(1.0, drives[d] + random.uniform(-0.02, 0.02)))

        hebbian_tick(g, action, location, drives, tick, surprise)

    print("\n── SUMMARY ──")
    s = g.summary()
    for k, v in s.items():
        if k == "strongest_edges":
            print(f"  strongest_edges:")
            for e in v[:3]:
                print(f"    {e['source']} ↔ {e['target']}  "
                      f"strength={e['strength']}  fires={e['co_activations']}")
        elif k == "most_activated":
            print(f"  most_activated:")
            for n in v[:3]:
                print(f"    {n['id']} ({n['type']})  activations={n['activations']}")
        else:
            print(f"  {k}: {v}")

    print("\n── GREG SPEAKS ──")
    print(f"  \"{g.speak()}\"")

    print("\n── WHAT DOES 'build' FIRE WITH? ──")
    for assoc in g.what_follows("build", 5):
        print(f"  {assoc['node']}  strength={assoc['strength']}  fires={assoc['co_activations']}")

    print("\n── WHERE DOES 'create' DRIVE? ──")
    for assoc in g.where_does("create", 5):
        print(f"  {assoc['node']}  strength={assoc['strength']}  fires={assoc['co_activations']}")

    print("\n✓ EXP_021 Hebbian Knowledge Graph ready")
    print("  Drop greg_hebbian.py into repo root")
    print("  greg_living.py already has the integration block — it will auto-load")