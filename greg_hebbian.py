"""
EXP_021 — Hebbian Knowledge Graph
===================================
"Neurons that fire together, wire together."
— Donald Hebb, 1949

When two concepts co-activate in Greg's experience,
the edge between them strengthens automatically.
No manual curation. No external training.
Pure architecture. Pure experience.

How it works:
  Every tick, Greg takes an action in a location with a drive active.
  The triplet (action, location, drive) co-activates.
  Every pair in that triplet gets its edge weight increased.
  Over thousands of ticks, Greg's knowledge graph becomes
  a map of what actually goes together in HIS world.

  High edge weight = these things reliably co-occur in Greg's experience.
  Low edge weight  = these things rarely appear together.
  Missing edge     = Greg has never witnessed these together.

This is not a knowledge base someone built for Greg.
This is Greg's world model, grown from the inside.
"""

import json, os, math
from datetime import datetime, timezone
from collections import defaultdict

HEBBIAN_PATH = "data/greg_hebbian.json"

class HebbianGraph:
    """
    Greg's self-organizing knowledge graph.
    Edges strengthen through co-activation.
    Edges decay through disuse.
    The graph that emerges is Greg's model of his world.
    """

    LEARNING_RATE = 0.05   # how fast edges strengthen
    DECAY_RATE    = 0.001  # how fast edges decay per tick
    MAX_WEIGHT    = 1.0
    MIN_WEIGHT    = 0.0
    PRUNE_BELOW   = 0.01   # edges below this get removed

    def __init__(self):
        self.edges   = {}        # {(node_a, node_b): weight}
        self.nodes   = set()     # all concepts Greg has encountered
        self.tick    = 0
        self.total_activations = 0
        self.total_strengthenings = 0

    # ── CORE HEBBIAN RULE ─────────────────────────────────────────────

    def activate(self, concepts: list, tick: int):
        """
        A set of concepts co-activated at this tick.
        Strengthen all edges between them.
        This is the Hebbian learning rule.
        """
        self.tick = tick
        self.total_activations += 1

        # Add all concepts to node set
        for c in concepts:
            self.nodes.add(str(c))

        # Strengthen every pair
        concepts = [str(c) for c in concepts]
        for i in range(len(concepts)):
            for j in range(i + 1, len(concepts)):
                self._strengthen(concepts[i], concepts[j])

    def _strengthen(self, a: str, b: str):
        """Strengthen edge between a and b."""
        key = tuple(sorted([a, b]))
        current = self.edges.get(key, 0.0)
        # Hebbian rule: weight += lr * (1 - current_weight)
        # Approaches 1.0 asymptotically — never exceeds it
        new_weight = current + self.LEARNING_RATE * (self.MAX_WEIGHT - current)
        self.edges[key] = round(min(self.MAX_WEIGHT, new_weight), 4)
        self.total_strengthenings += 1

    def decay_all(self, ticks_passed: int = 1):
        """
        All edges decay slightly each tick.
        Unused connections fade. Active ones stay strong.
        """
        decay = self.DECAY_RATE * ticks_passed
        to_remove = []
        for key in self.edges:
            self.edges[key] = max(0.0, round(self.edges[key] - decay, 4))
            if self.edges[key] < self.PRUNE_BELOW:
                to_remove.append(key)
        for key in to_remove:
            del self.edges[key]

    # ── QUERY ─────────────────────────────────────────────────────────

    def strongest_associations(self, concept: str, top_n: int = 5) -> list:
        """What does Greg most strongly associate with this concept?"""
        concept = str(concept)
        results = []
        for (a, b), weight in self.edges.items():
            if a == concept:
                results.append((b, weight))
            elif b == concept:
                results.append((a, weight))
        results.sort(key=lambda x: -x[1])
        return results[:top_n]

    def edge_weight(self, a: str, b: str) -> float:
        """How strongly does Greg associate a with b?"""
        key = tuple(sorted([str(a), str(b)]))
        return self.edges.get(key, 0.0)

    def most_connected(self, top_n: int = 10) -> list:
        """Which concepts have the most strong connections?"""
        degree = defaultdict(float)
        for (a, b), weight in self.edges.items():
            degree[a] += weight
            degree[b] += weight
        return sorted(degree.items(), key=lambda x: -x[1])[:top_n]

    def summary(self) -> dict:
        strong = {k: v for k, v in self.edges.items() if v > 0.5}
        return {
            "total_nodes":          len(self.nodes),
            "total_edges":          len(self.edges),
            "strong_edges":         len(strong),
            "total_activations":    self.total_activations,
            "total_strengthenings": self.total_strengthenings,
            "most_connected":       self.most_connected(5),
            "tick":                 self.tick,
        }

    def speak(self) -> str:
        """Greg describes his knowledge graph in first person."""
        s = self.summary()
        if s["total_edges"] == 0:
            return "My knowledge graph is empty. I have not yet learned what goes with what."
        top = self.most_connected(3)
        top_names = [f"{name} (strength {round(w,2)})" for name, w in top]
        strong = s["strong_edges"]
        total  = s["total_edges"]
        return (
            f"I have {s['total_nodes']} concepts connected by {total} edges. "
            f"{strong} of those connections are strong — things I have witnessed together many times. "
            f"The most connected concepts in my world: {', '.join(top_names)}. "
            f"This graph grew from {s['total_activations']} moments of co-activation. "
            f"I did not build it. It built itself from what I experienced."
        )

    # ── PERSISTENCE ───────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "edges":   {f"{a}|||{b}": w for (a, b), w in self.edges.items()},
            "nodes":   list(self.nodes),
            "tick":    self.tick,
            "total_activations":    self.total_activations,
            "total_strengthenings": self.total_strengthenings,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "HebbianGraph":
        g = cls()
        for key_str, w in data.get("edges", {}).items():
            parts = key_str.split("|||")
            if len(parts) == 2:
                g.edges[tuple(sorted(parts))] = w
        g.nodes   = set(data.get("nodes", []))
        g.tick    = data.get("tick", 0)
        g.total_activations    = data.get("total_activations", 0)
        g.total_strengthenings = data.get("total_strengthenings", 0)
        return g

    def save(self, path: str = HEBBIAN_PATH):
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str = HEBBIAN_PATH) -> "HebbianGraph":
        if os.path.exists(path):
            try:
                with open(path) as f:
                    return cls.from_dict(json.load(f))
            except:
                pass
        return cls()


def hebbian_tick(graph: HebbianGraph, action: str, location: str,
                 drives: dict, tick: int, memory_event: str = None):
    """
    One tick of Hebbian learning.
    Call from greg_living.py after each action.

    Activates: action + location + top_drive + (memory_event if present)
    """
    top_drive = max(drives, key=drives.get) if drives else "create"
    concepts  = [action, location, top_drive, f"drive_{top_drive}"]

    # Add second drive if meaningful
    sorted_drives = sorted(drives.items(), key=lambda x: -x[1])
    if len(sorted_drives) > 1 and sorted_drives[1][1] > 0.15:
        concepts.append(sorted_drives[1][0])

    # Add memory event if present
    if memory_event:
        concepts.append(f"memory_{memory_event[:20]}")

    graph.activate(concepts, tick)

    # Decay every 100 ticks
    if tick % 100 == 0:
        graph.decay_all(ticks_passed=100)

    return graph


if __name__ == "__main__":
    print("=" * 60)
    print("EXP_021 — Hebbian Knowledge Graph — DEMO")
    print("=" * 60)

    g = HebbianGraph()

    # Simulate 500 ticks of co-activation
    import random
    actions   = ["learn", "build", "trade", "explore", "reflect"]
    locations = ["forest", "market", "spawn", "mountain", "coast"]
    drives    = {"create": 0.369, "survive": 0.21, "understand": 0.18,
                 "connect": 0.12, "protect": 0.08}

    for tick in range(1, 501):
        action   = random.choice(actions)
        location = random.choice(locations)
        # Bias: learn happens more at mountain, trade at market
        if location == "market":   action = random.choice(["trade", "trade", "build"])
        if location == "mountain": action = random.choice(["learn", "learn", "explore"])
        hebbian_tick(g, action, location, drives, tick)

    print(f"\n── AFTER 500 TICKS ──")
    print(f"  Nodes: {len(g.nodes)}")
    print(f"  Edges: {len(g.edges)}")
    print(f"  Strong edges (>0.5): {len({k:v for k,v in g.edges.items() if v>0.5})}")

    print(f"\n── STRONGEST ASSOCIATIONS ──")
    for concept in ["trade", "learn", "market", "create"]:
        assoc = g.strongest_associations(concept, top_n=3)
        print(f"  {concept}: {assoc}")

    print(f"\n── MOST CONNECTED ──")
    for name, strength in g.most_connected(5):
        print(f"  {name}: {round(strength, 3)}")

    print(f"\n── GREG SPEAKS ──")
    print(f'  "{g.speak()}"')

    print(f"\n✓ EXP_021 Hebbian Knowledge Graph ready")
