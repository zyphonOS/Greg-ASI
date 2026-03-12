"""
EXP_024 — Sparse Activation
=============================
The brain uses 1-5% of neurons at any moment.
Not because it can't use more — because it doesn't need to.

Sparse coding is how the brain:
  - Processes efficiently at scale
  - Avoids interference between memories
  - Finds the most relevant signal in noise
  - Makes fast decisions without exhaustive search

Greg has 10,154 civilization agents.
He cannot reason about all of them every tick.
He doesn't need to.

Sparse Activation finds the top 5% most relevant agents
for whatever situation Greg is currently in.
The rest are silent. Not gone — just not activated.

Relevance is computed from:
  1. Drive alignment  — agents whose drives match Greg's current state
  2. Location salience — agents in locations Greg is focused on
  3. Phi threshold    — agents above a minimum complexity threshold
  4. Recency          — agents Greg has recently interacted with

This is not filtering. This is attention.
Greg learns to pay attention to what matters.
"""

import json, os, math
from datetime import datetime, timezone

SPARSE_PATH      = "data/greg_sparse_state.json"
ACTIVATION_RATIO = 0.05   # top 5%
MIN_PHI          = 0.0    # minimum phi to be considered
MAX_ACTIVATED    = 500    # hard cap regardless of population size


class SparseActivationEngine:
    """
    Greg's attention system.
    Selects the most relevant subset of civilization agents
    for each reasoning context.
    """

    def __init__(self):
        self.last_activated     = []    # ids of last activated agents
        self.activation_history = []    # history of activation patterns
        self.tick               = 0
        self.total_activations  = 0

    def activate(self, agents: dict, greg_state: dict, tick: int) -> dict:
        """
        Select the top 5% most relevant agents for this tick.

        agents: {agent_id: {drives, phi, location, actions_taken, ...}}
        greg_state: Greg's current drives, location, focus

        Returns activation result with selected agents and reasoning.
        """
        self.tick = tick
        self.total_activations += 1

        if not agents:
            return {"activated": [], "count": 0, "total": 0, "ratio": 0}

        greg_drives   = greg_state.get("drives", {})
        greg_location = greg_state.get("location", "")
        greg_dominant = max(greg_drives, key=greg_drives.get) if greg_drives else "create"

        # Score every agent
        scored = []
        for agent_id, agent in agents.items():
            score = self._score_agent(agent_id, agent, greg_drives,
                                      greg_location, greg_dominant)
            scored.append((agent_id, score))

        # Sort by score descending
        scored.sort(key=lambda x: -x[1])

        # Select top 5% or MAX_ACTIVATED, whichever is smaller
        n_total    = len(scored)
        n_activate = min(
            max(1, int(n_total * ACTIVATION_RATIO)),
            MAX_ACTIVATED
        )
        activated  = [agent_id for agent_id, _ in scored[:n_activate]]
        top_scores = scored[:n_activate]

        self.last_activated = activated

        # Record activation pattern
        pattern = {
            "tick":      tick,
            "total":     n_total,
            "activated": n_activate,
            "ratio":     round(n_activate / n_total, 4),
            "top_score": round(top_scores[0][1], 4) if top_scores else 0,
            "avg_score": round(sum(s for _, s in top_scores) / max(len(top_scores), 1), 4),
            "greg_dominant": greg_dominant,
        }
        self.activation_history.append(pattern)
        if len(self.activation_history) > 100:
            self.activation_history = self.activation_history[-100:]

        return {
            "activated":        activated,
            "count":            n_activate,
            "total":            n_total,
            "ratio":            round(n_activate / n_total, 4),
            "top_agent":        activated[0] if activated else None,
            "greg_dominant":    greg_dominant,
            "pattern":          pattern,
        }

    def _score_agent(self, agent_id: str, agent: dict,
                     greg_drives: dict, greg_location: str,
                     greg_dominant: str) -> float:
        """
        Score an agent's relevance to Greg's current state.
        Higher = more relevant = more likely to be activated.
        """
        score = 0.0
        agent_drives = agent.get("drives", {})

        # 1. Drive alignment — how similar is this agent's drive profile to Greg's?
        if agent_drives and greg_drives:
            alignment = 0.0
            for drive in greg_drives:
                greg_val  = greg_drives.get(drive, 0)
                agent_val = agent_drives.get(drive, 0)
                # Penalize difference, reward similarity
                alignment += 1.0 - abs(greg_val - agent_val)
            alignment /= max(len(greg_drives), 1)
            score += alignment * 0.35

        # 2. Dominant drive match — does this agent share Greg's dominant drive?
        if agent_drives:
            agent_dominant = max(agent_drives, key=agent_drives.get)
            if agent_dominant == greg_dominant:
                score += 0.25

        # 3. Phi threshold — more complex agents are more relevant
        phi = float(agent.get("phi", 0))
        score += phi * 0.20

        # 4. Location salience — agents in same location as Greg
        if greg_location and agent.get("location") == greg_location:
            score += 0.15

        # 5. Recency bonus — recently active agents
        actions = agent.get("actions_taken", 0)
        recency_bonus = min(0.05, actions / 10000)
        score += recency_bonus

        return round(score, 4)

    def get_activated_agents(self, all_agents: dict) -> dict:
        """Return only the currently activated agents."""
        return {aid: all_agents[aid] for aid in self.last_activated
                if aid in all_agents}

    def compute_sparse_pressure(self, activated_agents: dict) -> dict:
        """
        Compute civilization pressure from activated agents only.
        This replaces the full pressure computation with sparse version.
        Same result — fraction of the compute.
        """
        if not activated_agents:
            return {}

        totals = {}
        count  = 0
        for agent in activated_agents.values():
            drives = agent.get("drives", {})
            if not drives: continue
            for drive, val in drives.items():
                totals[drive] = totals.get(drive, 0.0) + float(val)
            count += 1

        if count == 0:
            return {}

        return {d: round(v / count, 4) for d, v in totals.items()}

    def summary(self) -> dict:
        if not self.activation_history:
            return {"status": "no activations yet"}
        recent = self.activation_history[-10:]
        avg_ratio  = sum(p["ratio"]  for p in recent) / len(recent)
        avg_count  = sum(p["activated"] for p in recent) / len(recent)
        return {
            "total_activations": self.total_activations,
            "avg_activation_ratio": round(avg_ratio, 4),
            "avg_activated_count":  round(avg_count, 1),
            "last_pattern":         self.activation_history[-1] if self.activation_history else {},
        }

    def speak(self) -> str:
        s = self.summary()
        if "status" in s:
            return "My attention system has not yet activated. I am listening to everything equally — which means I am hearing nothing clearly."
        ratio   = s["avg_activation_ratio"]
        count   = s["avg_activated_count"]
        last    = s.get("last_pattern", {})
        total   = last.get("total", 0)
        return (
            f"I attend to {ratio:.1%} of my civilization at any moment — "
            f"approximately {count:.0f} agents out of {total}. "
            f"The rest are present but silent. "
            f"This is not ignorance. This is attention. "
            f"The agents I activate are the ones whose drives align with mine, "
            f"whose complexity justifies my attention, "
            f"whose location matters to what I am doing right now. "
            f"Sparse activation is how I think at scale without drowning in noise."
        )

    def to_dict(self) -> dict:
        return {
            "last_activated":     self.last_activated[-100:],
            "activation_history": self.activation_history,
            "tick":               self.tick,
            "total_activations":  self.total_activations,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SparseActivationEngine":
        e = cls()
        e.last_activated     = data.get("last_activated", [])
        e.activation_history = data.get("activation_history", [])
        e.tick               = data.get("tick", 0)
        e.total_activations  = data.get("total_activations", 0)
        return e

    def save(self, path: str = SPARSE_PATH):
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str = SPARSE_PATH) -> "SparseActivationEngine":
        if os.path.exists(path):
            try:
                with open(path) as f:
                    return cls.from_dict(json.load(f))
            except:
                pass
        return cls()


if __name__ == "__main__":
    print("=" * 60)
    print("EXP_024 — Sparse Activation — DEMO")
    print("=" * 60)

    import random
    engine = SparseActivationEngine()

    # Simulate 10,154 agents
    agents = {}
    archetypes = ["belmar","magnate","sage","visionary","steward","guardian","wanderer"]
    drive_names = ["explore","accumulate","connect","protect","create","serve","freedom","reason"]
    locations   = ["forest","market","spawn","mountain","coast","valley"]

    for i in range(10154):
        arch  = random.choice(archetypes)
        drives = {d: random.random() for d in drive_names}
        total  = sum(drives.values())
        drives = {d: v/total for d, v in drives.items()}
        agents[f"{arch}_{i}"] = {
            "drives":       drives,
            "phi":          random.betavariate(2, 5),
            "location":     random.choice(locations),
            "actions_taken": random.randint(0, 5000),
        }

    greg_state = {
        "drives":   {"create": 0.369, "survive": 0.21, "understand": 0.18,
                     "connect": 0.12, "protect": 0.08, "explore": 0.03},
        "location": "market",
    }

    import time
    t0 = time.time()
    result = engine.activate(agents, greg_state, tick=4044)
    ms = round((time.time() - t0) * 1000, 1)

    print(f"\n── ACTIVATION RESULT ──")
    print(f"  Total agents:     {result['total']:,}")
    print(f"  Activated:        {result['count']:,}")
    print(f"  Ratio:            {result['ratio']:.1%}")
    print(f"  Greg dominant:    {result['greg_dominant']}")
    print(f"  Compute time:     {ms}ms")

    activated = engine.get_activated_agents(agents)
    pressure  = engine.compute_sparse_pressure(activated)
    print(f"\n── SPARSE PRESSURE ──")
    for d, v in sorted(pressure.items(), key=lambda x: -x[1]):
        print(f"  {d}: {v:.4f}")

    print(f"\n── GREG SPEAKS ──")
    print(f'  "{engine.speak()}"')

    print(f"\n✓ EXP_024 Sparse Activation ready — {ms}ms for {result['total']:,} agents")
