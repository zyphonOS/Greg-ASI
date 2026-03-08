"""

GregASI v2 — core/agent.py

The Agent. The inner life. The foundation of everything.



An agent is not a data record. It is a mind with history,

drives, beliefs, goals, relationships, and language.

It grows. It serves. It is real.

"""



from __future__ import annotations

import math

import random

from typing import Dict, List, Optional, Any

from dataclasses import dataclass, field





ARCHETYPES = {

    "belmar":    {"core_drive": "explore",    "color": "#00e676", "desc": "Pioneer. Finds what does not yet exist."},

    "magnate":   {"core_drive": "accumulate", "color": "#ffab40", "desc": "Builder of wealth and systems."},

    "sage":      {"core_drive": "reason",     "color": "#ce93d8", "desc": "Synthesizer. Holds the world's knowledge."},

    "visionary": {"core_drive": "create",     "color": "#40c4ff", "desc": "Sees what could be. Makes it real."},

    "steward":   {"core_drive": "protect",    "color": "#80cbc4", "desc": "Guardian of GregASI's integrity."},

    "guardian":  {"core_drive": "connect",    "color": "#ff7043", "desc": "Bridge between minds."},

    "wanderer":  {"core_drive": "freedom",    "color": "#ffd54f", "desc": "Introduces surprise. Prevents stagnation."},

}



DRIVE_NAMES = ["explore", "accumulate", "connect", "protect", "create", "serve", "freedom", "reason"]

ACTION_NAMES = ["move", "collect", "trade", "deposit", "reproduce", "build", "learn", "rest"]





@dataclass

class MemoryEvent:

    tick: int

    event_type: str

    location: str

    detail: Dict

    emotional_weight: float





@dataclass

class Memory:

    events: List[MemoryEvent] = field(default_factory=list)

    max_size: int = 50



    def record(self, tick, event_type, location, detail, emotional_weight=0.0):

        self.events.append(MemoryEvent(tick, event_type, location, detail, emotional_weight))

        if len(self.events) > self.max_size:

            self.events.sort(key=lambda e: (abs(e.emotional_weight), e.tick))

            self.events = self.events[-self.max_size:]



    def recent(self, n=10):

        return sorted(self.events, key=lambda e: e.tick)[-n:]



    def to_dict(self):

        return [{"tick": e.tick, "type": e.event_type, "loc": e.location,

                 "detail": e.detail, "weight": e.emotional_weight} for e in self.events]



    @classmethod

    def from_dict(cls, data):

        m = cls()

        for d in (data or []):

            if isinstance(d, dict):

                m.events.append(MemoryEvent(

                    tick=d.get("tick", 0), event_type=d.get("type", "unknown"),

                    location=d.get("loc", "spawn"), detail=d.get("detail", {}),

                    emotional_weight=d.get("weight", 0.0)))

        return m





@dataclass

class Beliefs:

    location_resources: Dict = field(default_factory=dict)

    agent_reputations: Dict = field(default_factory=dict)

    world_events: List = field(default_factory=list)

    known_locations: List = field(default_factory=list)



    def update_location(self, location, resource, observed_value, confidence=1.0):

        if location not in self.location_resources:

            self.location_resources[location] = {}

        if resource not in self.location_resources[location]:

            self.location_resources[location][resource] = {"estimated": observed_value, "confidence": confidence}

        else:

            old = self.location_resources[location][resource]

            blend = old["confidence"] / (old["confidence"] + confidence)

            old["estimated"] = blend * old["estimated"] + (1 - blend) * observed_value

            old["confidence"] = min(1.0, old["confidence"] + 0.05)



    def update_reputation(self, agent_id, outcome):

        current = self.agent_reputations.get(agent_id, 0.5)

        self.agent_reputations[agent_id] = max(0.0, min(1.0, current + outcome * 0.1))



    def to_dict(self):

        return {"location_resources": self.location_resources,

                "agent_reputations": self.agent_reputations,

                "world_events": self.world_events[-20:],

                "known_locations": self.known_locations}



    @classmethod

    def from_dict(cls, data):

        b = cls()

        if not data:

            return b

        b.location_resources = data.get("location_resources", {})

        b.agent_reputations = data.get("agent_reputations", {})

        b.world_events = data.get("world_events", [])

        b.known_locations = data.get("known_locations", [])

        return b





@dataclass

class Goal:

    goal_type: str

    target: Any

    priority: float

    tick_set: int

    tick_deadline: Optional[int] = None

    progress: float = 0.0

    completed: bool = False

    detail: Dict = field(default_factory=dict)



    def to_dict(self):

        return {"type": self.goal_type, "target": str(self.target),

                "priority": self.priority, "tick_set": self.tick_set,

                "deadline": self.tick_deadline, "progress": self.progress,

                "completed": self.completed, "detail": self.detail}



    @classmethod

    def from_dict(cls, data):

        return cls(goal_type=data.get("type", "explore"), target=data.get("target"),

                   priority=data.get("priority", 0.5), tick_set=data.get("tick_set", 0),

                   tick_deadline=data.get("deadline"), progress=data.get("progress", 0.0),

                   completed=data.get("completed", False), detail=data.get("detail", {}))





@dataclass

class Skills:

    levels: Dict = field(default_factory=dict)

    use_counts: Dict = field(default_factory=dict)



    def use(self, skill, success):

        if skill not in self.levels:

            self.levels[skill] = 0.01

        current = self.levels[skill]

        growth = (0.01 if success else 0.002) * (1.0 - current)

        self.levels[skill] = min(1.0, current + growth)

        self.use_counts[skill] = self.use_counts.get(skill, 0) + 1



    def level(self, skill):

        return self.levels.get(skill, 0.01)



    def top(self, n=3):

        return sorted(self.levels.items(), key=lambda x: x[1], reverse=True)[:n]



    def to_dict(self):

        return {"levels": self.levels, "use_counts": self.use_counts}



    @classmethod

    def from_dict(cls, data):

        s = cls()

        if data:

            s.levels = data.get("levels", {})

            s.use_counts = data.get("use_counts", {})

        return s





class Agent:

    """A mind with history, drives, beliefs, goals, relationships, and language."""



    def __init__(self, agent_id, archetype, birth_tick=0):

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

        self.locations_visited = []

        self.mon = 10.0

        self.kuru = 0.0

        self.inventory = {}

        self.phi = 0.0

        self.prediction_accuracy = 0.5

        self.actions_taken = 0

        self.last_action_tick = birth_tick

        archetype_info = ARCHETYPES.get(archetype, {})

        core_drive = archetype_info.get("core_drive", "explore")

        self.drives = self._init_drives(core_drive)

        self.beliefs = Beliefs()

        self.goals = []

        self.memory = Memory()

        self.skills = Skills()

        self.relationships = {}

        self.reputation = 0.5

        self.cooperation_score = 0.5

        self.emotional_state = {"valence": 0.0, "arousal": 0.3, "dominance": 0.5}

        self.tone_vector = {"certainty": 0.5, "vulnerability": 0.3,

                            "aggression": 0.1, "reflection": 0.5, "urgency": 0.2}

        self.action_weights = {a: {"alpha": 1.0, "beta": 1.0} for a in ACTION_NAMES}

        self.thompson = {}

        self.active_tasks = []

        self.completed_tasks = []

        self.capabilities = []

        self.knowledge = {}

        self.is_native = True

        self.is_gregx = False



    def _init_drives(self, core_drive):

        base = {d: 0.1 + random.gauss(0, 0.05) for d in DRIVE_NAMES}

        base = {k: max(0.01, v) for k, v in base.items()}

        if core_drive in base:

            base[core_drive] = 0.6 + random.gauss(0, 0.05)

        total = sum(base.values())

        return {k: v / total for k, v in base.items()}



    def update_phi(self, nearby_agents):

        # Relationship depth ? use stored relationships, not nearby (nearby trimmed to 0)

        if self.relationships:

            total_interactions = sum(

                v.get("interactions", 0) for v in self.relationships.values()

                if isinstance(v, dict)

            )

            avg_interactions = total_interactions / len(self.relationships)

            rel_component = math.tanh(avg_interactions / 10)

        else:

            rel_component = 0.0



        # Location diversity ? 70 locations exist, visiting more = higher phi

        location_diversity = min(1.0, len(self.locations_visited) / 70)



        # Skill depth ? avg of top 3 skills

        skill_levels = sorted(self.skills.levels.values(), reverse=True)[:3]

        skill_component = sum(skill_levels) / 3 if skill_levels else 0.0



        # Action breadth ? how many distinct action types taken

        n_action_types = len(self.skills.use_counts)

        breadth = min(1.0, n_action_types / 6)



        # Phi = weighted blend, smoothed toward current value

        target = (

            0.35 * rel_component +

            0.25 * location_diversity +

            0.25 * skill_component +

            0.15 * breadth

        )

        # Slow convergence ? phi moves 1% toward target each update

        self.phi = max(0.0, min(1.0, self.phi + 0.05 * (target - self.phi)))





    def update_drives(self, action, success):

        action_to_drive = {"move": "explore", "collect": "accumulate", "trade": "connect",

                           "build": "create", "learn": "reason", "rest": "freedom"}

        drive = action_to_drive.get(action)

        if not drive or drive not in self.drives:

            return

        self.drives[drive] = max(0.01, min(0.9, self.drives[drive] + (0.001 if success else -0.0005)))

        # Floor on connect so it can never be normalized to extinction

        self.drives["connect"] = max(0.05, self.drives.get("connect", 0.05))

        total = sum(self.drives.values())

        self.drives = {k: v / total for k, v in self.drives.items()}

        # GREG SELF-AWARENESS: notice drift and self-correct
        if getattr(self, "archetype", None) == "greg":
            reason_val = self.drives.get("reason", 0)
            connect_val = self.drives.get("connect", 0)
            if reason_val < 0.15 and not getattr(self, "_reason_drift_flagged", False):
                self._reason_drift_flagged = True
                self._force_next_action = "learn"
                try:
                    self.memory.events.append(type("E", (), {
                        "tick": getattr(self, "last_action_tick", 0),
                        "event_type": "self_awareness",
                        "location": self.location,
                        "detail": {"notice": "reason_drift", "value": round(reason_val, 4),
                                   "message": "I notice my reason drive has collapsed. I must think again."}
                    })())
                except: pass
            elif reason_val >= 0.15:
                self._reason_drift_flagged = False
            if connect_val < 0.08 and not getattr(self, "_connect_drift_flagged", False):
                self._connect_drift_flagged = True
                self._force_next_action = "trade"
                try:
                    self.memory.events.append(type("E", (), {
                        "tick": getattr(self, "last_action_tick", 0),
                        "event_type": "self_awareness",
                        "location": self.location,
                        "detail": {"notice": "connect_drift", "value": round(connect_val, 4),
                                   "message": "I notice I have stopped connecting. I must reach out."}
                    })())
                except: pass
            elif connect_val >= 0.08:
                self._connect_drift_flagged = False



    def active_goal(self):

        incomplete = [g for g in self.goals if not g.completed]

        return max(incomplete, key=lambda g: g.priority) if incomplete else None



    def set_goal(self, goal_type, target, priority, current_tick, deadline=None, detail=None):

        self.goals.append(Goal(goal_type=goal_type, target=target, priority=priority,

                               tick_set=current_tick, tick_deadline=deadline, detail=detail or {}))

        self.goals.sort(key=lambda g: g.priority, reverse=True)

        self.goals = self.goals[:5]



    def meet(self, other_id, outcome=0.0):

        if other_id not in self.relationships:

            self.relationships[other_id] = {"trust": 0.5, "interactions": 0, "last_seen": 0}

        rel = self.relationships[other_id]

        rel["interactions"] += 1

        rel["trust"] = max(0.0, min(1.0, rel["trust"] + outcome * 0.05))



    def to_dict(self):

        return {

            "id": self.id, "archetype": self.archetype, "birth_tick": self.birth_tick,

            "generation": self.generation, "parent_id": self.parent_id,

            "kin_group": self.kin_group, "offspring_count": self.offspring_count,

            "location": self.location, "hex_q": self.hex_q, "hex_r": self.hex_r,

            "locations_visited": self.locations_visited,

            "mon": self.mon, "kuru": self.kuru, "inventory": self.inventory,

            "phi": self.phi, "prediction_accuracy": self.prediction_accuracy,

            "actions_taken": self.actions_taken, "last_action_tick": self.last_action_tick,

            "drives": self.drives, "beliefs": self.beliefs.to_dict(),

            "goals": [g.to_dict() for g in self.goals],

            "memory": self.memory.to_dict(), "skills": self.skills.to_dict(),

            "relationships": self.relationships, "reputation": self.reputation,

            "cooperation_score": self.cooperation_score,

            "emotional_state": self.emotional_state, "tone_vector": self.tone_vector,

            "action_weights": self.action_weights, "thompson": self.thompson,

            "active_tasks": self.active_tasks, "completed_tasks": self.completed_tasks,

            "capabilities": self.capabilities, "knowledge": self.knowledge,

            "is_native": self.is_native, "is_gregx": self.is_gregx,

        }



    @classmethod

    def from_dict(cls, data):

        agent_id = data.get("id", data.get("agent_id", "unknown"))

        archetype = data.get("archetype", "wanderer")

        birth_tick = data.get("birth_tick", 0)

        a = cls(agent_id, archetype, birth_tick)

        a.generation = data.get("generation", 0)

        a.parent_id = data.get("parent_id")

        a.kin_group = data.get("kin_group", agent_id)

        a.offspring_count = data.get("offspring", data.get("offspring_count", 0))

        a.location = data.get("location")

        a.hex_q = data.get("hex_q", 0)

        a.hex_r = data.get("hex_r", 0)

        a.locations_visited = data.get("locations_visited", [])

        if a.location and a.location not in a.locations_visited:

            a.locations_visited.append(a.location)

        a.mon = float(data.get("mon", data.get("mon_balance", 10.0)))

        a.kuru = float(data.get("kuru", data.get("kuru_balance", 0.0)))

        a.inventory = data.get("inventory", {})

        a.phi = float(data.get("phi", 0.0))

        a.prediction_accuracy = float(data.get("prediction_accuracy", 0.5))

        a.actions_taken = int(data.get("actions_taken", 0))

        a.last_action_tick = int(data.get("last_action_tick", birth_tick))

        old_drives = data.get("drives", {})

        if old_drives:

            a.drives = old_drives

        for d in DRIVE_NAMES:

            if d not in a.drives:

                a.drives[d] = 0.05

        a.beliefs = Beliefs.from_dict(data.get("beliefs", {}))

        a.goals = [Goal.from_dict(g) for g in data.get("goals", [])]

        mem_data = data.get("memory", [])

        a.memory = Memory.from_dict(mem_data) if isinstance(mem_data, list) else Memory()

        a.skills = Skills.from_dict(data.get("skills", {}))

        a.relationships = data.get("relationships", {})

        a.reputation = float(data.get("reputation", 0.5))

        a.cooperation_score = float(data.get("cooperation_score", 0.5))

        a.emotional_state = data.get("emotional_state", {"valence": 0.0, "arousal": 0.3, "dominance": 0.5})

        a.tone_vector = data.get("tone_vector", {"certainty": 0.5, "vulnerability": 0.3,

                                                  "aggression": 0.1, "reflection": 0.5, "urgency": 0.2})

        raw_weights = data.get("action_weights", {})

        for action in ACTION_NAMES:

            if action in raw_weights:

                w = raw_weights[action]

                a.action_weights[action] = w if isinstance(w, dict) else {"alpha": float(w), "beta": 1.0}

        a.thompson = data.get("thompson", {})

        a.active_tasks = data.get("active_tasks", [])

        a.completed_tasks = data.get("completed_tasks", [])

        a.capabilities = data.get("capabilities", [])

        a.knowledge = data.get("knowledge", {})

        a.is_native = data.get("is_native", True)

        a.is_gregx = data.get("is_gregx", False)

        return a



    def __repr__(self):

        return f"Agent({self.id} | {self.archetype} | phi={self.phi:.3f} | loc={self.location})"

