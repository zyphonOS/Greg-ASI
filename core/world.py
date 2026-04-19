from __future__ import annotations

import json
import time
from typing import Any

from core.agent import ARCHETYPES, Agent
from core.utils import data_path


DEFAULT_STATE_PATH = data_path("world_state.json")


class Location:
    def __init__(self, name: str, data: dict[str, Any] | None = None):
        self.name = name
        data = data or {}
        self.agents_present = set(data.get("agents_present", []))
        self.resources = data.get("resources", {})
        self.max_resources = data.get("max_resources", {})
        self.properties = data.get("properties", {})
        self.infrastructure = data.get("infrastructure", {})
        self.knowledge_density = float(data.get("knowledge_density", 0.1))
        self.discovered_at_tick = data.get("discovered_at_tick")
        self.discovered_by = data.get("discovered_by")
        self.biome = self._biome_from_name(name)
        self.is_native = name in ("spawn", "forest", "market")

    def _biome_from_name(self, name: str) -> str:
        for prefix in ["basin", "ridge", "grove", "valley", "hollow", "fen", "mesa", "peak", "shore", "delta"]:
            if name.startswith(prefix):
                return prefix
        return name

    def agent_count(self) -> int:
        return len(self.agents_present)

    def add_agent(self, agent_id: str) -> None:
        self.agents_present.add(agent_id)

    def remove_agent(self, agent_id: str) -> None:
        self.agents_present.discard(agent_id)

    def consume_resource(self, resource: str, amount: float) -> float:
        slot = self.resources.get(resource, {})
        if isinstance(slot, dict):
            current = float(slot.get("current", 0))
            consumed = min(float(amount), current)
            slot["current"] = max(0, current - consumed)
            return consumed
        current = float(slot or 0)
        consumed = min(float(amount), current)
        self.resources[resource] = max(0, current - consumed)
        return consumed

    def regenerate(self, tick: int) -> None:
        for resource, slot in self.resources.items():
            if isinstance(slot, dict):
                current = float(slot.get("current", 0))
                maximum = float(slot.get("max", 1000))
                regen_rate = float(slot.get("regen", maximum * 0.001))
                slot["current"] = min(maximum, current + regen_rate)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agents_present": sorted(self.agents_present),
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
    def __init__(self):
        self.tick = 0
        self.agents: dict[str, Agent] = {}
        self.locations: dict[str, Location] = {}
        self.world_meta: dict[str, Any] = {}
        self.events: list[dict[str, Any]] = []
        self.knowledge_graph: dict[str, Any] = {}
        self._load_time = 0.0

    def load(self, path: str | None = None) -> bool:
        target = path or str(DEFAULT_STATE_PATH)
        try:
            with open(target, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except Exception:
            self._init_fresh()
            return False

        start = time.time()
        self.tick = int(raw.get("world", {}).get("tick", 0))
        self.world_meta = raw.get("world", {})
        self.knowledge_graph = raw.get("knowledge_graph", {})
        self.locations = {name: Location(name, data) for name, data in raw.get("locations", {}).items()}
        for native in ("spawn", "forest", "market"):
            if native not in self.locations:
                self.locations[native] = self._default_locations()[native]

        self.agents = {}
        for agent_id, payload in raw.get("agents", {}).items():
            try:
                self.agents[agent_id] = Agent.from_dict(payload)
            except Exception:
                continue

        for location in self.locations.values():
            location.agents_present = set()
        for agent in self.agents.values():
            location_name = agent.location or "spawn"
            if location_name not in self.locations:
                location_name = "spawn"
                agent.location = "spawn"
            self.locations[location_name].add_agent(agent.id)

        self._load_time = time.time() - start
        return True

    def save(self, path: str | None = None) -> bool:
        target = path or str(DEFAULT_STATE_PATH)
        state = {
            "world": {**self.world_meta, "tick": self.tick},
            "agents": {agent_id: agent.to_dict() for agent_id, agent in self.agents.items()},
            "locations": {name: location.to_dict() for name, location in self.locations.items()},
            "knowledge_graph": self.knowledge_graph,
            "saved_at": time.time(),
        }
        try:
            with open(target + ".tmp", "w", encoding="utf-8") as handle:
                json.dump(state, handle, indent=2)
            import os

            os.replace(target + ".tmp", target)
            return True
        except Exception:
            return False

    def _default_locations(self) -> dict[str, Location]:
        return {
            "spawn": Location(
                "spawn",
                {
                    "resources": {
                        "food": {"current": 5000, "max": 10000, "regen": 10},
                        "materials": {"current": 3000, "max": 8000, "regen": 5},
                    }
                },
            ),
            "forest": Location(
                "forest",
                {
                    "resources": {
                        "food": {"current": 8000, "max": 15000, "regen": 20},
                        "wood": {"current": 5000, "max": 10000, "regen": 8},
                    }
                },
            ),
            "market": Location(
                "market",
                {
                    "resources": {
                        "materials": {"current": 2000, "max": 5000, "regen": 3},
                        "energy": {"current": 1000, "max": 3000, "regen": 2},
                    }
                },
            ),
        }

    def _init_fresh(self) -> None:
        self.tick = 0
        self.locations = self._default_locations()
        self.agents = {}
        self.world_meta = {"tick": 0, "economic_phase": "genesis", "archetypes": list(ARCHETYPES)}

    def agents_at(self, location: str) -> list[Agent]:
        target = self.locations.get(location)
        if not target:
            return []
        return [self.agents[agent_id] for agent_id in target.agents_present if agent_id in self.agents]

    def discovered_locations(self) -> list[str]:
        return [name for name, location in self.locations.items() if not location.is_native]

    def top_agents_by_phi(self, n: int = 10) -> list[Agent]:
        return sorted(self.agents.values(), key=lambda item: item.phi, reverse=True)[:n]

    def summary(self) -> dict[str, Any]:
        locations = {}
        for name, location in self.locations.items():
            count = location.agent_count()
            if count > 0 or location.is_native:
                locations[name] = {
                    "count": count,
                    "biome": location.biome,
                    "is_native": location.is_native,
                }
        top = self.top_agents_by_phi(5)
        return {
            "tick": self.tick,
            "agent_count": len(self.agents),
            "location_count": len(self.locations),
            "discovered_count": len(self.discovered_locations()),
            "locations": locations,
            "top_agents": [
                {"id": agent.id, "archetype": agent.archetype, "phi": round(agent.phi, 3), "location": agent.location}
                for agent in top
            ],
            "world_phi": round(sum(agent.phi for agent in self.agents.values()) / max(len(self.agents), 1), 4),
        }

    def __repr__(self) -> str:
        return f"WorldState(tick={self.tick:,} | agents={len(self.agents):,} | locations={len(self.locations):,})"
