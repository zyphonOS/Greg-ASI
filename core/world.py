"""
GregASI v2 — core/world.py
The World. Loads the existing civilization history.
8,800 agents. 70 locations. 1.15M ticks. All preserved.
"""

from __future__ import annotations
import json
import orjson
import os
import time
from typing import Dict, List, Optional, Any
from core.agent import Agent, ARCHETYPES

# Path to the existing world state — the history
DEFAULT_STATE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "world_state.json"
)


class Location:
    """A place in the world."""

    def __init__(self, name: str, data: Dict = None):
        self.name = name
        data = data or {}

        self.agents_present: set = set(data.get("agents_present", []))
        self.resources: Dict = data.get("resources", {})
        self.max_resources: Dict = data.get("max_resources", {})
        self.properties: Dict = data.get("properties", {})
        self.infrastructure: Dict = data.get("infrastructure", {})
        self.knowledge_density: float = data.get("knowledge_density", 0.1)
        self.discovered_at_tick: Optional[int] = data.get("discovered_at_tick")
        self.discovered_by: Optional[str] = data.get("discovered_by")

        # Biome type from name prefix
        self.biome = self._biome_from_name(name)
        self.is_native = name in ("spawn", "forest", "market")

    def _biome_from_name(self, name: str) -> str:
        for prefix in ["basin", "ridge", "grove", "valley", "hollow",
                        "fen", "mesa", "peak", "shore", "delta"]:
            if name.startswith(prefix):
                return prefix
        return name  # spawn, forest, market

    def agent_count(self) -> int:
        return len(self.agents_present)  # O(1) for set

    def add_agent(self, agent_id: str):
        self.agents_present.add(agent_id)  # O(1)

    def remove_agent(self, agent_id: str):
        self.agents_present.discard(agent_id)  # O(1), no KeyError

    def get_resource(self, resource: str) -> float:
        r = self.resources.get(resource, {})
        if isinstance(r, dict):
            return float(r.get("current", 0))
        return float(r)

    def get_resource_max(self, resource: str) -> float:
        r = self.resources.get(resource, {})
        if isinstance(r, dict):
            return float(r.get("max", 1000))
        return float(self.max_resources.get(resource, 1000))

    def consume_resource(self, resource: str, amount: float) -> float:
        """Consume resource, return actual amount consumed."""
        r = self.resources.get(resource, {})
        if isinstance(r, dict):
            current = r.get("current", 0)
            consumed = min(float(amount), float(current))
            r["current"] = max(0, current - consumed)
            return consumed
        else:
            current = float(r) if r else 0
            consumed = min(amount, current)
            self.resources[resource] = max(0, current - consumed)
            return consumed

    def regenerate(self, tick: int):
        """Regenerate resources each tick."""
        for resource, r in self.resources.items():
            if isinstance(r, dict):
                current = r.get("current", 0)
                maximum = r.get("max", 1000)
                regen_rate = r.get("regen", maximum * 0.001)
                r["current"] = min(maximum, current + regen_rate)

    def to_dict(self) -> Dict:
        return {
            "agents_present": sorted(self.agents_present),  # set → list for JSON
            "resources": self.resources,
            "max_resources": self.max_resources,
            "properties": self.properties,
            "infrastructure": self.infrastructure,
            "knowledge_density": self.knowledge_density,
            "discovered_at_tick": self.discovered_at_tick,
            "discovered_by": self.discovered_by,
            "biome": self.biome,
        }


class WorldState:
    """
    The civilization. Loads from world_state.json.
    All 1.15M ticks of history, all 8,800 agents, all 70 locations.
    """

    def __init__(self):
        self.tick: int = 0
        self.agents: Dict[str, Agent] = {}
        self.locations: Dict[str, Location] = {}
        self.world_meta: Dict = {}
        self.events: List[Dict] = []
        self.knowledge_graph: Dict = {}
        self._load_time: float = 0

    def load(self, path: str = None) -> bool:
        """Load world state from JSON. Preserves all history."""
        path = path or DEFAULT_STATE_PATH

        if not os.path.exists(path):
            print(f"[WORLD] No state file at {path} — starting fresh")
            self._init_fresh()
            return False

        start = time.time()
        print(f"[WORLD] Loading civilization from {path}...")

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = orjson.loads(f.read())
        except Exception as e:
            print(f"[WORLD] Failed to load: {e}")
            self._init_fresh()
            return False

        # World meta
        world_data = raw.get("world", {})
        self.tick = world_data.get("tick", 0)
        self.world_meta = world_data
        self.knowledge_graph = raw.get("knowledge_graph", {})

        # Load locations
        locations_data = raw.get("locations", {})
        for loc_name, loc_data in locations_data.items():
            self.locations[loc_name] = Location(loc_name, loc_data)

        # Ensure native locations exist
        for native in ("spawn", "forest", "market"):
            if native not in self.locations:
                self.locations[native] = Location(native, {
                    "resources": {
                        "food": {"current": 5000, "max": 10000, "regen": 10},
                        "materials": {"current": 3000, "max": 8000, "regen": 5},
                    }
                })

        # Load agents — migrate from old format automatically
        agents_data = raw.get("agents", {})
        migrated = 0
        for agent_id, agent_data in agents_data.items():
            try:
                agent = Agent.from_dict(agent_data)
                self.agents[agent_id] = agent
                migrated += 1
            except Exception as e:
                pass  # Skip corrupted agents silently

        # Rebuild agents_present from agent.location
        # (set conversion loses the data — rebuild from source of truth)
        for loc in self.locations.values():
            loc.agents_present = set()
        orphans = 0
        for agent in self.agents.values():
            if agent.location:
                if agent.location in self.locations:
                    self.locations[agent.location].agents_present.add(agent.id)
                else:
                    # Agent references unknown location — put in spawn
                    agent.location = "spawn"
                    self.locations["spawn"].agents_present.add(agent.id)
                    orphans += 1

        self._load_time = time.time() - start

        print(f"[WORLD] Loaded in {self._load_time:.1f}s")
        print(f"  Tick:      {self.tick:,}")
        print(f"  Agents:    {len(self.agents):,}")
        print(f"  Locations: {len(self.locations):,}")
        if orphans:
            print(f"  Orphans:   {orphans} agents relocated to spawn")

        # Verify
        total_placed = sum(len(loc.agents_present) for loc in self.locations.values())
        print(f"  Placed:    {total_placed:,} agents in locations")

        return True

    def save(self, path: str = None) -> bool:
        """Save world state to JSON."""
        path = path or DEFAULT_STATE_PATH
        os.makedirs(os.path.dirname(path), exist_ok=True)

        try:
            def _trim_agent(d):
                k = d.get("knowledge", {})
                if isinstance(k, dict) and len(k) > 20:
                    d["knowledge"] = dict(list(k.items())[-20:])
                r = d.get("relationships", {})
                if isinstance(r, dict):
                    filtered = {k: v for k, v in r.items() if isinstance(v, dict) and v.get("interactions", 0) > 1}
                    d["relationships"] = dict(sorted(filtered.items(), key=lambda x: x[1].get("interactions", 0), reverse=True)[:50])
                b = d.get("beliefs", {})
                if isinstance(b, dict):
                    lr = b.get("location_resources", {})
                    if isinstance(lr, dict) and len(lr) > 10:
                        b["location_resources"] = dict(list(lr.items())[-10:])
                m = d.get("memory", [])
                if isinstance(m, list) and len(m) > 20:
                    d["memory"] = m[-20:]
                return d
            state = {
                "world": {**self.world_meta, "tick": self.tick},
                "agents": {aid: _trim_agent(a.to_dict()) for aid, a in self.agents.items()},
                "locations": {name: loc.to_dict() for name, loc in self.locations.items()},
                "knowledge_graph": self.knowledge_graph,
                "saved_at": time.time(),
            }
            tmp = path + ".tmp"
            with open(tmp, "wb") as f:
                f.write(orjson.dumps(state))
            os.replace(tmp, path)
            return True
        except Exception as e:
            print(f"[WORLD] Save failed: {e}")
            return False

    def _init_fresh(self):
        """Start fresh if no world state exists."""
        self.tick = 0
        self.locations = {
            "spawn": Location("spawn", {"resources": {
                "food": {"current": 5000, "max": 10000, "regen": 10},
                "materials": {"current": 3000, "max": 8000, "regen": 5},
            }}),
            "forest": Location("forest", {"resources": {
                "food": {"current": 8000, "max": 15000, "regen": 20},
                "wood": {"current": 5000, "max": 10000, "regen": 8},
            }}),
            "market": Location("market", {"resources": {
                "materials": {"current": 2000, "max": 5000, "regen": 3},
                "energy": {"current": 1000, "max": 3000, "regen": 2},
            }}),
        }
        self.world_meta = {"tick": 0, "economic_phase": "genesis"}

    # ── QUERIES ───────────────────────────────────────────────────────────

    def agents_at(self, location: str) -> List[Agent]:
        loc = self.locations.get(location)
        if not loc:
            return []
        return [self.agents[aid] for aid in loc.agents_present
                if aid in self.agents]

    def agent_count(self) -> int:
        return len(self.agents)

    def location_count(self) -> int:
        return len(self.locations)

    def discovered_locations(self) -> List[str]:
        return [name for name, loc in self.locations.items() if not loc.is_native]

    def top_agents_by_phi(self, n: int = 10) -> List[Agent]:
        return sorted(self.agents.values(), key=lambda a: a.phi, reverse=True)[:n]

    def summary(self) -> Dict:
        """Slim summary for API — not the full 24MB state."""
        loc_summary = {}
        for name, loc in self.locations.items():
            count = loc.agent_count()
            if count > 0 or loc.is_native:
                loc_summary[name] = {
                    "count": count,
                    "biome": loc.biome,
                    "is_native": loc.is_native,
                }

        top = self.top_agents_by_phi(5)

        return {
            "tick": self.tick,
            "agent_count": len(self.agents),
            "location_count": len(self.locations),
            "discovered_count": len(self.discovered_locations()),
            "locations": loc_summary,
            "top_agents": [
                {"id": a.id, "archetype": a.archetype, "phi": round(a.phi, 3),
                 "location": a.location}
                for a in top
            ],
            "world_phi": round(
                sum(a.phi for a in self.agents.values()) / max(len(self.agents), 1), 4
            ),
        }

    def __repr__(self):
        return (f"WorldState(tick={self.tick:,} | "
                f"agents={len(self.agents):,} | "
                f"locations={len(self.locations):,})")
