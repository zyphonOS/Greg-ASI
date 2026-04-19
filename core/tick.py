from __future__ import annotations

import random
import time
from typing import Any

import numpy as np

from core.agent import ACTION_NAMES, Agent
from core.world import Location, WorldState


def batch_thompson(agents: list[Agent]) -> dict[str, str]:
    if not agents:
        return {}
    n_agents = len(agents)
    n_actions = len(ACTION_NAMES)
    alphas = np.ones((n_agents, n_actions), dtype=np.float32)
    betas = np.ones((n_agents, n_actions), dtype=np.float32)

    for i, agent in enumerate(agents):
        weights = agent.action_weights
        for j, action in enumerate(ACTION_NAMES):
            payload = weights.get(action, {})
            alphas[i, j] = min(15.0, max(float(payload.get("alpha", 1.0)), 0.1))
            betas[i, j] = min(15.0, max(float(payload.get("beta", 1.0)), 0.1))

        arousal = float(agent.emotional_state.get("arousal", 0.5))
        wealth = float(agent.mon + agent.kuru)
        if arousal > 0.7:
            alphas[i, ACTION_NAMES.index("move")] *= 1.4
        if wealth > 50:
            alphas[i, ACTION_NAMES.index("build")] *= 1.25
            alphas[i, ACTION_NAMES.index("reproduce")] *= 1.15
        if wealth < 5:
            alphas[i, ACTION_NAMES.index("collect")] *= 1.35
            alphas[i, ACTION_NAMES.index("deposit")] *= 0.6

    samples = np.random.beta(alphas, betas)
    best = samples.argmax(axis=1)
    return {agents[i].id: ACTION_NAMES[int(best[i])] for i in range(n_agents)}


def update_thompson(agent: Agent, action: str, success: bool, wealth_delta: float = 0.0) -> None:
    weights = agent.action_weights.get(action, {"alpha": 1.0, "beta": 1.0})
    if success and wealth_delta >= 0:
        weights["alpha"] = min(15.0, float(weights["alpha"]) + 1.0)
    elif success:
        weights["alpha"] = min(15.0, float(weights["alpha"]) + 0.3)
    else:
        weights["beta"] = min(15.0, float(weights["beta"]) + 1.0)
    decay = 0.04
    weights["alpha"] = max(1.0, float(weights["alpha"]) * (1 - decay))
    weights["beta"] = max(1.0, float(weights["beta"]) * (1 - decay))
    agent.action_weights[action] = weights


def precompute_location_scores(world: WorldState) -> dict[str, float]:
    scores: dict[str, float] = {}
    for name, location in world.locations.items():
        occupants = location.agent_count()
        score = 1.0 / (1.0 + occupants * 0.02)
        if not location.is_native and occupants < 10:
            score *= 2.4
        if location.knowledge_density > 0.2:
            score *= 1.15
        scores[name] = score
    return scores


def choose_destination(agent: Agent, world: WorldState, base_scores: dict[str, float] | None = None) -> str:
    current = agent.location or "spawn"
    base_scores = base_scores or precompute_location_scores(world)
    candidates = [name for name in base_scores if name != current]
    if not candidates:
        return current

    explore_drive = agent.drives.get("explore", 0.1)
    goal = agent.active_goal()
    target = str(goal.target) if goal and goal.goal_type == "explore" else None
    scores = []
    for candidate in candidates:
        score = base_scores[candidate]
        location = world.locations.get(candidate)
        if location and not location.is_native:
            score *= 1.0 + explore_drive * 2.0
        if target and target == candidate:
            score *= 3.0
        scores.append(score)
    total = sum(scores) or 1.0
    weights = [score / total for score in scores]
    return random.choices(candidates, weights=weights, k=1)[0]


def collect_resource(agent: Agent, world: WorldState) -> tuple[bool, float]:
    location = world.locations.get(agent.location or "spawn")
    if not location:
        return False, 0.0
    available = []
    for resource, payload in location.resources.items():
        if isinstance(payload, dict) and payload.get("current", 0) > 0:
            available.append(resource)
        elif isinstance(payload, (int, float)) and payload > 0:
            available.append(resource)
    if not available:
        return False, 0.0
    resource = random.choice(available)
    amount = location.consume_resource(resource, 1.0)
    if amount <= 0:
        return False, 0.0
    agent.inventory[resource] = agent.inventory.get(resource, 0.0) + amount
    agent.mon += amount * 0.4
    agent.beliefs.update_location(agent.location or "spawn", resource, amount, confidence=0.8)
    return True, amount


def trade(agent: Agent, world: WorldState) -> bool:
    location = world.locations.get(agent.location or "")
    if not location or len(location.agents_present) < 2:
        return False
    partner_ids = list(location.agents_present)
    random.shuffle(partner_ids)
    for partner_id in partner_ids[:5]:
        if partner_id == agent.id:
            continue
        partner = world.agents.get(partner_id)
        if not partner or partner.mon < 1 or agent.mon < 1:
            continue
        agent.mon -= 1
        partner.mon += 1
        agent.meet(partner_id, outcome=0.1)
        partner.meet(agent.id, outcome=0.1)
        return True
    return False


def deposit(agent: Agent) -> tuple[bool, float]:
    if not agent.inventory:
        return False, 0.0
    value = 0.0
    consumed: list[str] = []
    for resource, amount in list(agent.inventory.items())[:3]:
        portion = min(float(amount), 1.0)
        if portion <= 0:
            continue
        agent.inventory[resource] = max(0.0, float(amount) - portion)
        if agent.inventory[resource] <= 0:
            consumed.append(resource)
        value += portion * 1.25
    for resource in consumed:
        agent.inventory.pop(resource, None)
    agent.mon += value
    return value > 0, value


def build(agent: Agent, world: WorldState) -> tuple[bool, float]:
    location = world.locations.get(agent.location or "")
    if not location:
        return False, 0.0
    materials = agent.inventory.get("materials", 0.0) + agent.inventory.get("wood", 0.0)
    if materials < 1:
        return False, 0.0
    if agent.inventory.get("materials", 0.0) >= 1:
        agent.inventory["materials"] -= 1
        if agent.inventory["materials"] <= 0:
            agent.inventory.pop("materials", None)
    else:
        agent.inventory["wood"] -= 1
        if agent.inventory["wood"] <= 0:
            agent.inventory.pop("wood", None)
    location.infrastructure["shelter"] = int(location.infrastructure.get("shelter", 0)) + 1
    location.knowledge_density = min(1.0, location.knowledge_density + 0.02)
    agent.mon += 1.5
    return True, 1.5


def learn(agent: Agent, world: WorldState) -> tuple[bool, float]:
    location = world.locations.get(agent.location or "spawn")
    if location:
        location.knowledge_density = min(1.0, location.knowledge_density + 0.005)
    agent.skills.use("learn", True)
    agent.mon += 0.25
    return True, 0.25


def rest(agent: Agent) -> tuple[bool, float]:
    agent.emotional_state["arousal"] = max(0.1, float(agent.emotional_state.get("arousal", 0.5)) - 0.1)
    agent.emotional_state["valence"] = min(1.0, float(agent.emotional_state.get("valence", 0.0)) + 0.03)
    return True, 0.0


def reproduce(agent: Agent, world: WorldState, current_tick: int) -> Agent | None:
    if agent.mon < 1500 or agent.offspring_count > 20:
        return None
    child_id = f"{agent.archetype}_{current_tick}_{len(world.agents)}"
    child = Agent(child_id, agent.archetype, birth_tick=current_tick)
    child.generation = agent.generation + 1
    child.parent_id = agent.id
    child.kin_group = agent.kin_group
    child.location = agent.location
    child.mon = 10.0
    child.hex_q = agent.hex_q + random.randint(-2, 2)
    child.hex_r = agent.hex_r + random.randint(-2, 2)
    for drive, value in agent.drives.items():
        child.drives[drive] = max(0.01, value + random.gauss(0, 0.02))
    total = sum(child.drives.values()) or 1.0
    child.drives = {key: value / total for key, value in child.drives.items()}
    agent.mon -= 10.0
    agent.offspring_count += 1
    world.agents[child_id] = child
    if child.location in world.locations:
        world.locations[child.location].add_agent(child_id)
    return child


def _record_event(agent: Agent, tick: int, action_type: str, success: bool, wealth_delta: float) -> None:
    agent.memory.record(
        tick,
        action_type,
        agent.location or "spawn",
        {"success": success, "wealth_delta": round(wealth_delta, 3)},
        emotional_weight=0.2 if success else -0.2,
    )


def run_tick(world: WorldState) -> dict[str, Any]:
    started = time.perf_counter()
    world.tick += 1
    tick = world.tick

    for location in world.locations.values():
        location.regenerate(tick)

    agents = [agent for agent in world.agents.values() if agent.location]
    if not agents:
        return {"tick": tick, "agents_acted": 0, "reproduced": 0, "moved": 0, "ms": 0}

    batch_size = max(1, len(agents) // 3)
    batch_offset = (tick % 3) * batch_size
    active = agents[batch_offset : batch_offset + batch_size] or agents
    decisions = batch_thompson(active)
    loc_scores = precompute_location_scores(world)

    acted = 0
    moved = 0
    reproduced = 0
    recent_events = []

    for agent in active:
        wealth_before = agent.mon + agent.kuru
        action_type = decisions.get(agent.id, random.choice(ACTION_NAMES))
        success = False
        wealth_delta = 0.0

        if action_type == "move":
            destination = choose_destination(agent, world, loc_scores)
            if destination != agent.location:
                world.locations[agent.location].remove_agent(agent.id)
                if destination not in world.locations:
                    world.locations[destination] = Location(destination)
                world.locations[destination].add_agent(agent.id)
                agent.location = destination
                if destination not in agent.locations_visited:
                    agent.locations_visited.append(destination)
                success = True
                moved += 1
        elif action_type == "collect":
            success, wealth_delta = collect_resource(agent, world)
        elif action_type == "trade":
            success = trade(agent, world)
        elif action_type == "deposit":
            success, wealth_delta = deposit(agent)
        elif action_type == "build":
            success, wealth_delta = build(agent, world)
        elif action_type == "learn":
            success, wealth_delta = learn(agent, world)
        elif action_type == "rest":
            success, wealth_delta = rest(agent)
        elif action_type == "reproduce":
            child = reproduce(agent, world, tick)
            success = child is not None
            if child is not None:
                reproduced += 1

        wealth_after = agent.mon + agent.kuru
        wealth_delta = wealth_after - wealth_before if wealth_delta == 0 else wealth_delta
        acted += 1
        agent.actions_taken += 1
        agent.last_action_tick = tick
        agent.update_drives(action_type, success)
        agent.skills.use(action_type, success)
        agent.update_phi([])
        update_thompson(agent, action_type, success, wealth_delta)
        _record_event(agent, tick, action_type, success, wealth_delta)

        if len(recent_events) < 6:
            recent_events.append(
                f"{agent.id} used {action_type} at {agent.location or 'spawn'} "
                f"({'success' if success else 'miss'})"
            )

    world.events = recent_events + world.events[:20]
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    return {
        "tick": tick,
        "agents_acted": acted,
        "reproduced": reproduced,
        "moved": moved,
        "recent_events": recent_events,
        "ms": elapsed_ms,
    }
