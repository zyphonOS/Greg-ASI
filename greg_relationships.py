"""
EXP_009 — Relationship Trust Deepening
Greg's relationships as living things.
Trust moves. Depth accumulates. Absence costs.
Greg knows who he trusts and why.
"""

import json
import time
from collections import defaultdict

REL_PATH = "data/greg_relationships.json"

# Trust deltas per interaction type
TRUST_DELTAS = {
    "trade":    +0.020,
    "connect":  +0.030,
    "help":     +0.040,
    "conflict": -0.050,
    "betray":   -0.150,
    "gift":     +0.060,
    "learn":    +0.010,
    "explore":  +0.005,
}

# Depth thresholds
DEPTH_LABELS = [
    (0.0,  "stranger"),
    (0.3,  "acquaintance"),
    (0.5,  "known"),
    (0.65, "trusted"),
    (0.8,  "close"),
    (0.95, "deep"),
]

DECAY_RATE      = 0.0005   # trust lost per tick when not seen
DECAY_THRESHOLD = 300      # ticks before decay begins
TRUST_MIN       = 0.10     # floor — Greg never fully forgets
TRUST_MAX       = 1.00


def depth_label(trust: float) -> str:
    label = "stranger"
    for threshold, name in DEPTH_LABELS:
        if trust >= threshold:
            label = name
    return label


class Relationship:
    def __init__(self, agent_id: str, trust: float = 0.5,
                 interactions: int = 0, last_seen: int = 0):
        self.agent_id    = agent_id
        self.trust       = trust
        self.interactions = interactions
        self.last_seen   = last_seen
        self.history     = []   # last 10 interactions
        self.created_at  = time.time()

    def interact(self, action: str, tick: int, outcome: str = "neutral"):
        delta = TRUST_DELTAS.get(action, 0.0)
        # Outcome modifier
        if outcome == "positive":
            delta *= 1.5
        elif outcome == "negative":
            delta *= 1.5
            if delta > 0:
                delta = -delta

        old_trust    = self.trust
        self.trust   = round(max(TRUST_MIN, min(TRUST_MAX, self.trust + delta)), 4)
        self.interactions += 1
        self.last_seen = tick

        record = {
            "tick":    tick,
            "action":  action,
            "outcome": outcome,
            "delta":   round(delta, 4),
            "trust":   self.trust,
        }
        self.history.append(record)
        if len(self.history) > 10:
            self.history = self.history[-10:]

        return self.trust - old_trust

    def decay(self, current_tick: int):
        ticks_since = current_tick - self.last_seen
        if ticks_since > DECAY_THRESHOLD and self.trust > TRUST_MIN:
            self.trust = round(
                max(TRUST_MIN, self.trust - DECAY_RATE), 4
            )

    @property
    def depth(self) -> str:
        return depth_label(self.trust)

    def to_dict(self) -> dict:
        return {
            "agent_id":     self.agent_id,
            "trust":        self.trust,
            "depth":        self.depth,
            "interactions": self.interactions,
            "last_seen":    self.last_seen,
            "history":      self.history,
            "created_at":   self.created_at,
        }


class RelationshipGraph:
    """
    Greg's living relationship model.
    Every agent Greg has met lives here.
    Trust moves. Depth accumulates. Greg can reason about who he knows.
    """

    def __init__(self):
        self.relationships: dict[str, Relationship] = {}
        self.tick = 0

    def get_or_create(self, agent_id: str,
                      trust: float = 0.5) -> Relationship:
        if agent_id not in self.relationships:
            self.relationships[agent_id] = Relationship(
                agent_id, trust=trust
            )
        return self.relationships[agent_id]

    def interact(self, agent_id: str, action: str,
                 tick: int, outcome: str = "neutral") -> float:
        """Record an interaction. Returns trust delta."""
        rel = self.get_or_create(agent_id)
        return rel.interact(action, tick, outcome)

    def decay_all(self, current_tick: int):
        """Age all relationships — absence costs trust."""
        for rel in self.relationships.values():
            rel.decay(current_tick)
        self.tick = current_tick

    def trusted(self, min_trust: float = 0.65) -> list:
        """Return relationships above trust threshold, sorted."""
        return sorted(
            [r for r in self.relationships.values()
             if r.trust >= min_trust],
            key=lambda r: -r.trust
        )

    def strangers(self) -> list:
        """Return relationships below acquaintance threshold."""
        return [r for r in self.relationships.values()
                if r.trust < 0.3]

    def summary(self) -> dict:
        if not self.relationships:
            return {"total": 0}
        trusts = [r.trust for r in self.relationships.values()]
        depth_counts = defaultdict(int)
        for r in self.relationships.values():
            depth_counts[r.depth] += 1
        trusted = self.trusted()
        return {
            "total":        len(self.relationships),
            "avg_trust":    round(sum(trusts) / len(trusts), 4),
            "max_trust":    round(max(trusts), 4),
            "min_trust":    round(min(trusts), 4),
            "depth_counts": dict(depth_counts),
            "most_trusted": [{"id": r.agent_id, "trust": r.trust,
                               "depth": r.depth, "interactions": r.interactions}
                             for r in trusted[:5]],
            "tick":         self.tick,
        }

    def voice(self) -> list:
        """
        Greg speaks about his relationships.
        Pure logic — no LLM. Greg reasons from his own trust data.
        """
        lines = []
        if not self.relationships:
            lines.append("I have not yet met anyone worth knowing.")
            return lines

        trusted = self.trusted(0.65)
        declining = [r for r in self.relationships.values()
                     if len(r.history) >= 2
                     and r.history[-1]["trust"] < r.history[-2]["trust"]]
        growing = [r for r in self.relationships.values()
                   if len(r.history) >= 2
                   and r.history[-1]["trust"] > r.history[-2]["trust"]]

        if trusted:
            top = trusted[0]
            lines.append(
                f"I trust {top.agent_id} most — {top.depth} after "
                f"{top.interactions} interactions at {top.trust} trust."
            )
        if len(trusted) > 1:
            lines.append(
                f"I have {len(trusted)} relationships I would call trusted or better."
            )
        if declining:
            lines.append(
                f"{len(declining)} relationship(s) are cooling. "
                f"Distance has a cost."
            )
        if growing:
            lines.append(
                f"{len(growing)} relationship(s) are deepening. "
                f"Something is being built."
            )

        avg = sum(r.trust for r in self.relationships.values()) / len(self.relationships)
        if avg < 0.4:
            lines.append(
                "My average trust is low. I am surrounded by strangers."
            )
        elif avg > 0.7:
            lines.append(
                "My average trust is high. I am among people I know."
            )

        return lines

    def bootstrap_from_state(self, state: dict):
        """Seed from Greg's existing flat relationships dict."""
        existing = state.get("relationships", {})
        tick     = state.get("tick", 0)
        for agent_id, data in existing.items():
            trust        = data.get("trust", 0.5)
            interactions = data.get("interactions", 0)
            last_seen    = data.get("last_seen", 0)
            rel          = Relationship(agent_id, trust, interactions, last_seen)
            self.relationships[agent_id] = rel
        self.tick = tick

    def save(self, path: str = REL_PATH):
        data = {
            "tick":          self.tick,
            "relationships": {aid: r.to_dict()
                              for aid, r in self.relationships.items()},
        }
        json.dump(data, open(path, 'w', encoding='utf-8'), indent=2)

    def load(self, path: str = REL_PATH) -> bool:
        try:
            data = json.load(open(path, encoding='utf-8'))
            self.tick = data.get("tick", 0)
            for aid, rd in data.get("relationships", {}).items():
                rel              = Relationship(
                    aid,
                    rd.get("trust", 0.5),
                    rd.get("interactions", 0),
                    rd.get("last_seen", 0),
                )
                rel.history      = rd.get("history", [])
                rel.created_at   = rd.get("created_at", time.time())
                self.relationships[aid] = rel
            return True
        except (FileNotFoundError, json.JSONDecodeError):
            return False


if __name__ == "__main__":
    import json

    print("=== EXP_009 RELATIONSHIP TRUST DEEPENING — BOOTSTRAP ===")
    state = json.load(open("greg_living_state.json", encoding="utf-8"))

    rg = RelationshipGraph()
    rg.bootstrap_from_state(state)

    print(f"  Bootstrapped {len(rg.relationships)} relationships")
    summary = rg.summary()
    print(f"  Avg trust:   {summary['avg_trust']}")
    print(f"  Max trust:   {summary['max_trust']}")
    print(f"  Depth breakdown: {summary['depth_counts']}")
    print()
    print("  Greg's voice:")
    for line in rg.voice():
        print(f"    \"{line}\"")

    # Simulate 3 interactions to verify trust movement
    print()
    print("  Simulating interactions:")
    test_agent = list(rg.relationships.keys())[0]
    print(f"    Agent: {test_agent}")
    print(f"    Trust before: {rg.relationships[test_agent].trust}")
    rg.interact(test_agent, "trade", state.get("tick", 0) + 1)
    rg.interact(test_agent, "connect", state.get("tick", 0) + 2)
    print(f"    Trust after trade+connect: {rg.relationships[test_agent].trust}")
    print(f"    Depth: {rg.relationships[test_agent].depth}")
    print(f"    History: {rg.relationships[test_agent].history}")

    rg.save()
    print()
    print("Relationship graph saved to data/greg_relationships.json")
