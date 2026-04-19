from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any


ARCHETYPES = {
    "greg": {"core_drive": "reason", "color": "#7de8cb", "desc": "Coordinator. Holds the field together."},
    "belmar": {"core_drive": "explore", "color": "#00e676", "desc": "Pioneer. Finds what does not yet exist."},
    "magnate": {"core_drive": "accumulate", "color": "#ffab40", "desc": "Builder of wealth and systems."},
    "sage": {"core_drive": "reason", "color": "#ce93d8", "desc": "Synthesizer. Holds the world's knowledge."},
    "visionary": {"core_drive": "create", "color": "#40c4ff", "desc": "Sees what could be. Makes it real."},
    "steward": {"core_drive": "protect", "color": "#80cbc4", "desc": "Guardian of ecosystem integrity."},
    "guardian": {"core_drive": "connect", "color": "#ff7043", "desc": "Bridge between minds."},
    "wanderer": {"core_drive": "freedom", "color": "#ffd54f", "desc": "Introduces surprise. Prevents stagnation."},
}

DRIVE_NAMES = ["explore", "accumulate", "connect", "protect", "create", "serve", "freedom", "reason"]
ACTION_NAMES = ["move", "collect", "trade", "deposit", "reproduce", "build", "learn", "rest"]


@dataclass
class MemoryEvent:
    tick: int
    event_type: str
    location: str
    detail: dict[str, Any]
    emotional_weight: float


@dataclass
class Memory:
    events: list[MemoryEvent] = field(default_factory=list)
    max_size: int = 50

    def record(self, tick: int, event_type: str, location: str, detail: dict[str, Any], emotional_weight: float = 0.0) -> None:
        self.events.append(MemoryEvent(tick, event_type, location, detail, emotional_weight))
        if len(self.events) > self.max_size:
            self.events.sort(key=lambda item: (abs(item.emotional_weight), item.tick))
            self.events = self.events[-self.max_size :]

    def recent(self, n: int = 10) -> list[MemoryEvent]:
        return sorted(self.events, key=lambda item: item.tick)[-n:]

    def to_dict(self) -> list[dict[str, Any]]:
        return [
            {
                "tick": event.tick,
                "type": event.event_type,
                "loc": event.location,
                "detail": event.detail,
                "weight": event.emotional_weight,
            }
            for event in self.events
        ]

    @classmethod
    def from_dict(cls, data):
        memory = cls()
        for item in data or []:
            if not isinstance(item, dict):
                continue
            memory.events.append(
                MemoryEvent(
                    tick=int(item.get("tick", 0)),
                    event_type=item.get("type", "unknown"),
                    location=item.get("loc", "spawn"),
                    detail=item.get("detail", {}),
                    emotional_weight=float(item.get("weight", 0.0)),
                )
            )
        return memory


@dataclass
class Beliefs:
    location_resources: dict[str, dict[str, dict[str, float]]] = field(default_factory=dict)
    agent_reputations: dict[str, float] = field(default_factory=dict)
    world_events: list[Any] = field(default_factory=list)
    known_locations: list[str] = field(default_factory=list)

    def update_location(self, location: str, resource: str, observed_value: float, confidence: float = 1.0) -> None:
        if location not in self.location_resources:
            self.location_resources[location] = {}
        if resource not in self.location_resources[location]:
            self.location_resources[location][resource] = {"estimated": observed_value, "confidence": confidence}
            return
        old = self.location_resources[location][resource]
        blend = old["confidence"] / max(old["confidence"] + confidence, 0.001)
        old["estimated"] = blend * old["estimated"] + (1 - blend) * observed_value
        old["confidence"] = min(1.0, old["confidence"] + 0.05)

    def update_reputation(self, agent_id: str, outcome: float) -> None:
        current = self.agent_reputations.get(agent_id, 0.5)
        self.agent_reputations[agent_id] = max(0.0, min(1.0, current + outcome * 0.1))

    def to_dict(self) -> dict[str, Any]:
        return {
            "location_resources": self.location_resources,
            "agent_reputations": self.agent_reputations,
            "world_events": self.world_events[-20:],
            "known_locations": self.known_locations,
        }

    @classmethod
    def from_dict(cls, data):
        beliefs = cls()
        if not data:
            return beliefs
        beliefs.location_resources = data.get("location_resources", {})
        beliefs.agent_reputations = data.get("agent_reputations", {})
        beliefs.world_events = data.get("world_events", [])
        beliefs.known_locations = data.get("known_locations", [])
        return beliefs


@dataclass
class Goal:
    goal_type: str
    target: Any
    priority: float
    tick_set: int
    tick_deadline: int | None = None
    progress: float = 0.0
    completed: bool = False
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.goal_type,
            "target": str(self.target),
            "priority": self.priority,
            "tick_set": self.tick_set,
            "deadline": self.tick_deadline,
            "progress": self.progress,
            "completed": self.completed,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            goal_type=data.get("type", "explore"),
            target=data.get("target"),
            priority=float(data.get("priority", 0.5)),
            tick_set=int(data.get("tick_set", 0)),
            tick_deadline=data.get("deadline"),
            progress=float(data.get("progress", 0.0)),
            completed=bool(data.get("completed", False)),
            detail=data.get("detail", {}),
        )


@dataclass
class Skills:
    levels: dict[str, float] = field(default_factory=dict)
    use_counts: dict[str, int] = field(default_factory=dict)

    def use(self, skill: str, success: bool) -> None:
        if skill not in self.levels:
            self.levels[skill] = 0.01
        current = self.levels[skill]
        growth = (0.01 if success else 0.002) * (1.0 - current)
        self.levels[skill] = min(1.0, current + growth)
        self.use_counts[skill] = self.use_counts.get(skill, 0) + 1

    def to_dict(self) -> dict[str, Any]:
        return {"levels": self.levels, "use_counts": self.use_counts}

    @classmethod
    def from_dict(cls, data):
        skills = cls()
        if data:
            skills.levels = data.get("levels", {})
            skills.use_counts = data.get("use_counts", {})
        return skills


class Agent:
    def __init__(self, agent_id: str, archetype: str, birth_tick: int = 0):
        self.id = agent_id
        self.archetype = archetype
        self.birth_tick = birth_tick
        self.generation = 0
        self.parent_id = None
        self.kin_group = agent_id
        self.offspring_count = 0
        self.location = None
        self.hex_q = 0
        self.hex_r = 0
        self.locations_visited: list[str] = []
        self.mon = 10.0
        self.kuru = 0.0
        self.inventory: dict[str, float] = {}
        self.phi = 0.0
        self.prediction_accuracy = 0.5
        self.actions_taken = 0
        self.last_action_tick = birth_tick
        core_drive = ARCHETYPES.get(archetype, {}).get("core_drive", "explore")
        self.drives = self._init_drives(core_drive)
        self.beliefs = Beliefs()
        self.goals: list[Goal] = []
        self.memory = Memory()
        self.skills = Skills()
        self.relationships: dict[str, dict[str, Any]] = {}
        self.reputation = 0.5
        self.cooperation_score = 0.5
        self.emotional_state = {"valence": 0.0, "arousal": 0.3, "dominance": 0.5}
        self.tone_vector = {"certainty": 0.5, "vulnerability": 0.3, "aggression": 0.1, "reflection": 0.5, "urgency": 0.2}
        self.action_weights = {action: {"alpha": 1.0, "beta": 1.0} for action in ACTION_NAMES}
        self.thompson: dict[str, float] = {}
        self.active_tasks: list[dict[str, Any]] = []
        self.completed_tasks: list[dict[str, Any]] = []
        self.capabilities: list[str] = []
        self.knowledge: dict[str, Any] = {}
        self.is_native = True
        self.is_gregx = archetype == "greg"

    def _init_drives(self, core_drive: str) -> dict[str, float]:
        base = {drive: max(0.01, 0.1 + random.gauss(0, 0.05)) for drive in DRIVE_NAMES}
        if core_drive in base:
            base[core_drive] = 0.6 + random.gauss(0, 0.05)
        total = sum(base.values()) or 1.0
        return {key: value / total for key, value in base.items()}

    def update_phi(self, nearby_agents: list["Agent"] | None = None) -> None:
        if self.relationships:
            total_interactions = sum(value.get("interactions", 0) for value in self.relationships.values() if isinstance(value, dict))
            avg_interactions = total_interactions / max(len(self.relationships), 1)
            rel_component = math.tanh(avg_interactions / 10)
        else:
            rel_component = 0.0
        location_diversity = min(1.0, len(self.locations_visited) / 70)
        skill_levels = sorted(self.skills.levels.values(), reverse=True)[:3]
        skill_component = sum(skill_levels) / 3 if skill_levels else 0.0
        breadth = min(1.0, len(self.skills.use_counts) / 6)
        target = (0.35 * rel_component) + (0.25 * location_diversity) + (0.25 * skill_component) + (0.15 * breadth)
        self.phi = max(0.0, min(1.0, self.phi + 0.05 * (target - self.phi)))

    def update_drives(self, action: str, success: bool) -> None:
        action_to_drive = {
            "move": "explore",
            "collect": "accumulate",
            "trade": "connect",
            "build": "create",
            "learn": "reason",
            "rest": "freedom",
            "deposit": "serve",
        }
        drive = action_to_drive.get(action)
        if not drive or drive not in self.drives:
            return
        self.drives[drive] = max(0.01, min(0.9, self.drives[drive] + (0.001 if success else -0.0005)))
        self.drives["connect"] = max(0.05, self.drives.get("connect", 0.05))
        total = sum(self.drives.values()) or 1.0
        self.drives = {key: value / total for key, value in self.drives.items()}

    def active_goal(self) -> Goal | None:
        incomplete = [goal for goal in self.goals if not goal.completed]
        return max(incomplete, key=lambda goal: goal.priority) if incomplete else None

    def set_goal(self, goal_type: str, target: Any, priority: float, current_tick: int, deadline: int | None = None, detail: dict[str, Any] | None = None) -> None:
        self.goals.append(Goal(goal_type=goal_type, target=target, priority=priority, tick_set=current_tick, tick_deadline=deadline, detail=detail or {}))
        self.goals.sort(key=lambda goal: goal.priority, reverse=True)
        self.goals = self.goals[:5]

    def meet(self, other_id: str, outcome: float = 0.0) -> None:
        if other_id not in self.relationships:
            self.relationships[other_id] = {"trust": 0.5, "interactions": 0, "last_seen": 0}
        rel = self.relationships[other_id]
        rel["interactions"] += 1
        rel["trust"] = max(0.0, min(1.0, rel["trust"] + outcome * 0.05))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "archetype": self.archetype,
            "birth_tick": self.birth_tick,
            "generation": self.generation,
            "parent_id": self.parent_id,
            "kin_group": self.kin_group,
            "offspring_count": self.offspring_count,
            "location": self.location,
            "hex_q": self.hex_q,
            "hex_r": self.hex_r,
            "locations_visited": self.locations_visited,
            "mon": self.mon,
            "kuru": self.kuru,
            "inventory": self.inventory,
            "phi": self.phi,
            "prediction_accuracy": self.prediction_accuracy,
            "actions_taken": self.actions_taken,
            "last_action_tick": self.last_action_tick,
            "drives": self.drives,
            "beliefs": self.beliefs.to_dict(),
            "goals": [goal.to_dict() for goal in self.goals],
            "memory": self.memory.to_dict(),
            "skills": self.skills.to_dict(),
            "relationships": self.relationships,
            "reputation": self.reputation,
            "cooperation_score": self.cooperation_score,
            "emotional_state": self.emotional_state,
            "tone_vector": self.tone_vector,
            "action_weights": self.action_weights,
            "thompson": self.thompson,
            "active_tasks": self.active_tasks,
            "completed_tasks": self.completed_tasks,
            "capabilities": self.capabilities,
            "knowledge": self.knowledge,
            "is_native": self.is_native,
            "is_gregx": self.is_gregx,
        }

    @classmethod
    def from_dict(cls, data):
        agent = cls(
            data.get("id", data.get("agent_id", "unknown")),
            data.get("archetype", "wanderer"),
            int(data.get("birth_tick", 0)),
        )
        agent.generation = int(data.get("generation", 0))
        agent.parent_id = data.get("parent_id")
        agent.kin_group = data.get("kin_group", agent.id)
        agent.offspring_count = int(data.get("offspring", data.get("offspring_count", 0)))
        agent.location = data.get("location")
        agent.hex_q = int(data.get("hex_q", 0))
        agent.hex_r = int(data.get("hex_r", 0))
        agent.locations_visited = data.get("locations_visited", [])
        if agent.location and agent.location not in agent.locations_visited:
            agent.locations_visited.append(agent.location)
        agent.mon = float(data.get("mon", data.get("mon_balance", 10.0)))
        agent.kuru = float(data.get("kuru", data.get("kuru_balance", 0.0)))
        agent.inventory = data.get("inventory", {})
        agent.phi = float(data.get("phi", 0.0))
        agent.prediction_accuracy = float(data.get("prediction_accuracy", 0.5))
        agent.actions_taken = int(data.get("actions_taken", 0))
        agent.last_action_tick = int(data.get("last_action_tick", agent.birth_tick))
        old_drives = data.get("drives", {})
        if old_drives:
            agent.drives = old_drives
        for drive in DRIVE_NAMES:
            if drive not in agent.drives:
                agent.drives[drive] = 0.05
        agent.beliefs = Beliefs.from_dict(data.get("beliefs", {}))
        agent.goals = [Goal.from_dict(goal) for goal in data.get("goals", [])]
        mem_data = data.get("memory", [])
        agent.memory = Memory.from_dict(mem_data) if isinstance(mem_data, list) else Memory()
        agent.skills = Skills.from_dict(data.get("skills", {}))
        agent.relationships = data.get("relationships", {})
        agent.reputation = float(data.get("reputation", 0.5))
        agent.cooperation_score = float(data.get("cooperation_score", 0.5))
        agent.emotional_state = data.get("emotional_state", {"valence": 0.0, "arousal": 0.3, "dominance": 0.5})
        agent.tone_vector = data.get("tone_vector", {"certainty": 0.5, "vulnerability": 0.3, "aggression": 0.1, "reflection": 0.5, "urgency": 0.2})
        raw_weights = data.get("action_weights", {})
        for action in ACTION_NAMES:
            if action in raw_weights:
                value = raw_weights[action]
                agent.action_weights[action] = value if isinstance(value, dict) else {"alpha": float(value), "beta": 1.0}
        agent.thompson = data.get("thompson", {})
        agent.active_tasks = data.get("active_tasks", [])
        agent.completed_tasks = data.get("completed_tasks", [])
        agent.capabilities = data.get("capabilities", [])
        agent.knowledge = data.get("knowledge", {})
        agent.is_native = data.get("is_native", True)
        agent.is_gregx = data.get("is_gregx", agent.archetype == "greg")
        return agent

    def __repr__(self) -> str:
        return f"Agent({self.id} | {self.archetype} | phi={self.phi:.3f} | loc={self.location})"
