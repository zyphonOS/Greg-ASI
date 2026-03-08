"""

GregASI v2 — core/tick.py

The heartbeat of the civilization.

One tick = every agent senses, decides, acts, grows.

Target: <100ms for 8,800 agents.

"""



from __future__ import annotations

import random

import time

import math

import numpy as np

from typing import Dict, List, Optional, Tuple

from core.agent import Agent, ACTION_NAMES, DRIVE_NAMES

from core.world import WorldState, Location





# ── BATCH ML INFERENCE ────────────────────────────────────────────────────────



_model = None

_model_type = None



def _load_ml_model():

    """Load sequence model once, cache it."""

    global _model, _model_type

    if _model is not None:

        return _model, _model_type



    import os

    # Try to find models relative to this file or in old backend

    search_paths = [

        os.path.join(os.path.dirname(__file__), "..", "data", "sequence_model.npz"),

        os.path.join(os.path.dirname(__file__), "..", "..", "backend", "sequence_model.npz"),

    ]

    for path in search_paths:

        if os.path.exists(path):

            try:

                _model = dict(np.load(path, allow_pickle=True))

                _model_type = "sequence"

                print(f"[TICK] Loaded ML model from {path}")

                return _model, _model_type

            except Exception as e:

                pass



    print("[TICK] No ML model found — using Thompson sampling only")

    return None, None





def batch_ml_predict(agents: List[Agent]) -> Dict[str, str]:

    """

    Batch forward pass — all agents in one matrix operation.

    Returns {agent_id: action_string}

    """

    model, model_type = _load_ml_model()



    if model is None or "W1" not in model:

        return {}



    n = len(agents)

    if n == 0:

        return {}





    # Only run ML for agents with sufficient memory history

    # Cache recent events once per agent

    agent_records = {a.id: a.memory.recent(5) for a in agents}

    ml_agents = [a for a in agents if len(agent_records[a.id]) >= 3]

    if not ml_agents:

        return {}

    agents = ml_agents

    n = len(agents)

    # Build feature matrix — encode each agent's recent history

    FEATURE_DIM = 40

    X = np.zeros((n, FEATURE_DIM), dtype=np.float32)



    action_map = {a: i for i, a in enumerate(ACTION_NAMES)}

    loc_map = {"spawn": 0, "forest": 1, "market": 2}



    for i, agent in enumerate(agents):

        records = agent_records[agent.id]

        # Pack last 5 actions into feature vector

        for j, event in enumerate(records[-5:]):

            base = j * 8

            act_idx = action_map.get(event.event_type, 0)

            X[i, base] = act_idx / max(len(ACTION_NAMES) - 1, 1)

            X[i, base + 1] = loc_map.get(event.location, 2) / 2.0

            X[i, base + 2] = float(event.detail.get("success", 0))

            X[i, base + 3] = min(1.0, float(event.detail.get("wealth_delta", 0)) / 100.0)

        # Agent state features

        X[i, 35] = min(1.0, agent.mon / 1000.0)

        X[i, 36] = agent.phi

        X[i, 37] = agent.emotional_state.get("arousal", 0.3)

        X[i, 38] = agent.emotional_state.get("valence", 0.0) * 0.5 + 0.5

        X[i, 39] = agent.drives.get("explore", 0.1)



    # Single forward pass

    try:

        W1, b1 = model["W1"], model["b1"]

        H = np.maximum(0, X @ W1.T + b1)

        if "W2" in model:

            W2, b2 = model["W2"], model["b2"]

            H = np.maximum(0, H @ W2.T + b2)

        if "W3" in model:

            W3, b3 = model["W3"], model["b3"]

            logits = H @ W3.T + b3

        else:

            logits = H

        TEMPERATURE = 2.5

        exp_l = np.exp((logits - logits.max(axis=1, keepdims=True)) / TEMPERATURE)

        probs = exp_l / exp_l.sum(axis=1, keepdims=True)

        best = probs.argmax(axis=1)

        # Only use ML when confident ? margin between top 2 logits > 0.5

        margins = logits.max(axis=1) - np.partition(logits, -2, axis=1)[:, -2]

        result = {}

        for i, agent in enumerate(agents):

            if margins[i] > 0.05:

                result[agent.id] = ACTION_NAMES[min(int(best[i]), len(ACTION_NAMES) - 1)]

        return result

    except Exception as e:

        return {}





# ── THOMPSON SAMPLING (vectorized numpy) ─────────────────────────────────────



def thompson_choose(agent: Agent) -> str:

    """Single-agent Thompson — used as fallback only."""

    weights = agent.action_weights

    alphas = np.array([max(weights.get(a, {}).get("alpha", 1.0), 0.1) for a in ACTION_NAMES])

    betas  = np.array([max(weights.get(a, {}).get("beta",  1.0), 0.1) for a in ACTION_NAMES])

    samples = np.random.beta(alphas, betas)

    return ACTION_NAMES[int(samples.argmax())]





def batch_thompson(agents: List[Agent]) -> Dict[str, str]:

    """

    Vectorized Thompson sampling for all agents at once.

    One np.random.beta call instead of 140K Python random calls.

    Returns {agent_id: action_string}

    """

    n = len(agents)

    na = len(ACTION_NAMES)



    # Build alpha/beta matrices (n_agents, n_actions)

    alphas = np.ones((n, na), dtype=np.float32)

    betas  = np.ones((n, na), dtype=np.float32)



    # Build alpha/beta arrays with list comprehensions — faster than nested loop

    action_idx = {a: j for j, a in enumerate(ACTION_NAMES)}

    move_idx    = action_idx.get("move", 0)

    repro_idx   = action_idx.get("reproduce", 4)

    collect_idx = action_idx.get("collect", 1)

    trade_idx   = action_idx.get("trade", 2)



    for i, agent in enumerate(agents):

        weights = agent.action_weights

        arousal = agent.emotional_state.get("arousal", 0.5)

        valence = agent.emotional_state.get("valence", 0.0)

        wealth  = agent.mon + agent.kuru



        for j, action in enumerate(ACTION_NAMES):

            w = weights.get(action, {})

            alphas[i, j] = min(15.0, max(w.get("alpha", 1.0) if isinstance(w, dict) else 1.0, 0.1))

            betas[i, j]  = max(w.get("beta",  1.0) if isinstance(w, dict) else 1.0, 0.1)



    # Apply contextual boosts as vectorized numpy ops (no Python loop)

    arousal_arr = np.array([a.emotional_state.get("arousal", 0.5) for a in agents], dtype=np.float32)

    valence_arr = np.array([a.emotional_state.get("valence", 0.0) for a in agents], dtype=np.float32)

    wealth_arr  = np.array([a.mon + a.kuru for a in agents], dtype=np.float32)



    alphas[:, move_idx]    *= np.where(arousal_arr > 0.7, 1.5, 1.0)

    alphas[:, repro_idx]   *= np.where(wealth_arr > 1200, 1.2, np.where(wealth_arr > 800, 1.05, 1.0))

    betas[:, repro_idx]    *= np.where(wealth_arr < 150, 3.0, 1.0)

    # betas[:, repro_idx] *= ... removed ? was causing population explosion

    alphas[:, collect_idx] *= np.where(valence_arr < -0.3, 1.3, 1.0)

    alphas[:, trade_idx]   *= np.where(valence_arr > 0.3, 1.2, 1.0)



    # Single vectorized beta sample — replaces 140K gammavariate calls

    samples = np.random.beta(alphas, betas)

    best = samples.argmax(axis=1)



    return {agents[i].id: ACTION_NAMES[int(best[i])] for i in range(n)}





def update_thompson(agent: Agent, action: str, success: bool, wealth_delta: float = 0):

    """Update Thompson weights after action outcome."""

    w = agent.action_weights.get(action, {"alpha": 1.0, "beta": 1.0})

    if success and wealth_delta >= 0:

        w["alpha"] = min(15.0, w["alpha"] + 1.0)

    elif success:

        w["alpha"] = min(15.0, w["alpha"] + 0.3)

    else:

        w["beta"] = min(15.0, w["beta"] + 1.0)

    DECAY = 0.04

    w["alpha"] = max(1.0, w["alpha"] * (1 - DECAY))

    w["beta"] = max(1.0, w["beta"] * (1 - DECAY))

    agent.action_weights[action] = w





# ── DESTINATION SELECTION ─────────────────────────────────────────────────────



def precompute_location_scores(world: WorldState) -> Dict[str, float]:

    """

    Compute base location attractiveness scores ONCE per tick.

    Shared across all agents — eliminates O(n*locations) per tick.

    """

    scores = {}

    for name, loc in world.locations.items():

        occupants = loc.agent_count()

        is_biome = not loc.is_native

        s = 1.0 / (1.0 + occupants * 0.005)

        if is_biome and occupants < 20:

            s *= 3.0  # base biome bonus (explore drive multiplier applied per-agent)

        scores[name] = s

    return scores





def choose_destination(agent: Agent, world: WorldState,

                       base_scores: Dict[str, float] = None) -> str:

    """

    Choose where to move using pre-computed base scores.

    Agent's explore drive and goals add personal adjustments.

    """

    current = agent.location or "spawn"

    if base_scores is None:

        base_scores = precompute_location_scores(world)



    candidates = [l for l in base_scores if l != current]

    if not candidates:

        return current



    explore_drive = agent.drives.get("explore", 0.1)

    goal = agent.active_goal()

    goal_target = str(goal.target) if goal and goal.goal_type == "explore" else None



    scores = []

    for loc_name in candidates:

        s = base_scores[loc_name]

        # Personal adjustments

        loc = world.locations.get(loc_name)

        if loc and not loc.is_native:

            s *= (1.0 + explore_drive * 2.0)

        if goal_target and goal_target == loc_name:

            s *= 3.0

        scores.append(s)



    total = sum(scores) or 1.0

    weights = [s / total for s in scores]

    return random.choices(candidates, weights=weights, k=1)[0]





# ── RESOURCE COLLECTION ───────────────────────────────────────────────────────



def collect_resource(agent: Agent, world: WorldState) -> Tuple[bool, float]:

    """Agent collects a resource from their location."""

    loc = world.locations.get(agent.location or "spawn")

    if not loc:

        return False, 0.0



    # Find available resources

    available = []

    for res, r in loc.resources.items():

        if isinstance(r, dict) and r.get("current", 0) > 0:

            available.append(res)

        elif isinstance(r, (int, float)) and r > 0:

            available.append(res)



    if not available:

        return False, 0.0



    resource = random.choice(available)

    amount = loc.consume_resource(resource, 1.0)



    if amount > 0:

        agent.inventory[resource] = agent.inventory.get(resource, 0) + amount

        agent.mon += amount * 0.5  # resources have monetary value

        agent.beliefs.update_location(agent.location, resource, amount, confidence=0.8)

        return True, amount



    return False, 0.0





# ── TRADE ────────────────────────────────────────────────────────────────────



def trade(agent: Agent, world: WorldState, native_ids: List[str],

         loc_lists: Dict[str, list] = None) -> bool:

    """Agent trades with another agent at same location."""

    loc = world.locations.get(agent.location or "")

    if not loc or len(loc.agents_present) < 2:

        return False



    present_list = (loc_lists or {}).get(agent.location) or list(loc.agents_present)

    if len(present_list) < 2:

        return False

    candidates = random.sample(present_list, min(5, len(present_list)))



    for partner_id in candidates:

        if partner_id == agent.id:

            continue

        partner = world.agents.get(partner_id)

        if partner and partner.mon >= 1 and agent.mon >= 1:

            agent.mon -= 1

            partner.mon += 1

            agent.meet(partner_id, outcome=0.1)

            partner.meet(agent.id, outcome=0.1)

            return True

    return False





# ── REPRODUCE ─────────────────────────────────────────────────────────────────



def reproduce(agent: Agent, world: WorldState, current_tick: int) -> Optional[Agent]:

    """Agent reproduces if wealthy enough."""

    if agent.mon < 1500 or agent.offspring_count > 50:

        return None



    # Choose archetype for child — weighted by parent's archetype

    archetype_pool = list(world.agents.values())

    if len(archetype_pool) > 100:

        archetype_pool = random.sample(archetype_pool, 100)

    child_archetype = agent.archetype  # default: same



    child_id = f"{child_archetype}_{current_tick}_{len(world.agents)}"

    child = Agent(child_id, child_archetype, birth_tick=current_tick)

    child.generation = agent.generation + 1

    child.parent_id = agent.id

    child.kin_group = agent.kin_group

    child.location = agent.location

    child.mon = 10.0

    child.hex_q = agent.hex_q + random.randint(-2, 2)

    child.hex_r = agent.hex_r + random.randint(-2, 2)



    # Inherit drives with mutation

    for drive in DRIVE_NAMES:

        parent_val = agent.drives.get(drive, 0.1)

        child.drives[drive] = max(0.01, parent_val + random.gauss(0, 0.02))

    total = sum(child.drives.values())

    child.drives = {k: v / total for k, v in child.drives.items()}



    # Inherit action weights

    for action in ACTION_NAMES:

        pw = agent.action_weights.get(action, {"alpha": 1.0, "beta": 1.0})

        child.action_weights[action] = {

            "alpha": min(8.0, max(1.0, pw["alpha"] * 0.7 + random.gauss(0, 0.05))),

            "beta": max(1.0, pw["beta"] * 0.7 + random.gauss(0, 0.05)),

        }



    agent.mon -= 10.0

    agent.offspring_count += 1



    # Add to world

    world.agents[child_id] = child

    if agent.location in world.locations:

        world.locations[agent.location].add_agent(child_id)



    return child





# ── THE TICK ──────────────────────────────────────────────────────────────────



def run_tick(world: WorldState) -> Dict:

    """

    One tick of the civilization.

    Every agent senses, decides, acts, grows.

    Target: <100ms for 8,800 agents.

    """

    t_start = time.perf_counter()

    world.tick += 1

    tick = world.tick



    # Death check ? remove agents that exceeded lifespan

    to_remove = []

    for a in list(world.agents.values()):

        if not a.is_native or a.archetype == 'greg':

            continue

        lifespan = 300000 + int(getattr(a, 'phi', 0) * 200000)

        if (tick - a.birth_tick) > lifespan:

            to_remove.append(a.id)

    for aid in to_remove:

        a = world.agents.pop(aid, None)

        if a and a.location and a.location in world.locations:

            world.locations[a.location].agents_present.discard(aid)

        # Death legacy ? write elder trace to knowledge graph

        if a and a.phi > 0.4:

            legacy_key = f"elder:{a.id}"

            world.knowledge_graph[legacy_key] = {

                "id": a.id,

                "archetype": a.archetype,

                "born": a.birth_tick,

                "died": tick,

                "lifespan": tick - a.birth_tick,

                "phi": round(a.phi, 4),

                "generation": a.generation,

                "offspring": a.offspring_count,

                "locations_visited": len(a.locations_visited),

                "relationships": len(a.relationships),

                "mon": round(a.mon, 1),

                "top_skill": max(a.skills.levels, key=a.skills.levels.get) if a.skills.levels else None,

                "last_location": a.location,

                "cooperation_score": round(

                    a.drives.get("connect", 0) * 0.4 +

                    min(1.0, len(a.relationships) / 20.0) * 0.35 +

                    a.skills.levels.get("trade", 0) * 0.25, 4

                ),

            }



    all_native = [a for a in world.agents.values()

                  if (a.is_native or a.archetype == 'greg') and a.location]



    if not all_native:

        return {"tick": tick, "agents_acted": 0, "ms": 0}



    # Rotating batch: process 25% of agents per tick

    # Every agent acts every 4 ticks — same statistical behavior, 4x speed

    batch_size = max(1, len(all_native) // 4)

    batch_offset = (tick % 4) * batch_size

    native_agents = all_native[batch_offset: batch_offset + batch_size]



    # ── BATCH INFERENCE: vectorized Thompson ────────────────────────────

    # ML inference every 6th tick -- amortizes 52ms cost to ~8ms avg

    ml_predictions = batch_ml_predict(native_agents) if tick % 6 == 0 else {}

    thompson_predictions = batch_thompson(native_agents)



    # ── PER-AGENT ACTION LOOP ─────────────────────────────────────────────

    acted = 0

    reproduced = 0

    moved = 0



    native_ids = [a.id for a in native_agents]



    # Pre-compute location scores ONCE — shared across all 8,800 agents

    loc_scores = precompute_location_scores(world)



    # Pre-convert agents_present sets to lists ONCE — eliminates sorted() per agent

    loc_lists: Dict[str, list] = {

        name: list(loc.agents_present)

        for name, loc in world.locations.items()

    }



    for agent in native_agents:

        agent_kuru = getattr(agent, 'kuru', 0.0)

        wealth_before = agent.mon + agent_kuru



        # Choose action: ML prediction if available, else vectorized Thompson

        # GREG SELF-CORRECTION: override if drift flagged
        if getattr(agent, '_force_next_action', None) and getattr(agent, 'archetype', None) == 'greg':
            action_type = agent._force_next_action
            agent._force_next_action = None
        else:
            action_type = ml_predictions.get(agent.id) or thompson_predictions.get(agent.id) or thompson_choose(agent)



        success = False

        wealth_delta = 0.0



        if action_type == "move":

            dest = choose_destination(agent, world, loc_scores)

            if dest != agent.location:

                old_loc = agent.location

                world.locations[old_loc].remove_agent(agent.id)

                if dest not in world.locations:

                    world.locations[dest] = Location(dest)

                world.locations[dest].add_agent(agent.id)

                agent.location = dest

                if dest not in agent.locations_visited:

                    agent.locations_visited.append(dest)

                agent.memory.record(tick, "move", dest,

                                    {"from": old_loc, "to": dest}, 0.1)

                agent.skills.use("explore", True)

                success = True

                moved += 1



        elif action_type == "collect":

            success, amount = collect_resource(agent, world)

            if success:

                agent.skills.use("collect", True)

                agent.memory.record(tick, "collect", agent.location,

                                    {"amount": amount, "success": True}, 0.2)

            else:

                agent.skills.use("collect", False)



        elif action_type == "trade":

            success = trade(agent, world, native_ids, loc_lists)

            agent.skills.use("trade", success)

            agent.memory.record(tick, "trade", agent.location,

                                {"success": success}, 0.3 if success else 0.1)



        elif action_type == "reproduce":

            child = reproduce(agent, world, tick)

            if child:

                success = True

                reproduced += 1

                agent.memory.record(tick, "reproduce", agent.location,

                                    {"child_id": child.id}, 0.8)



        elif action_type == "learn":

            # Agent learns from their location

            loc = world.locations.get(agent.location or "")

            if loc:

                agent.knowledge[f"loc_{agent.location}_{tick}"] = {

                    "resources": {r: loc.get_resource(r) for r in loc.resources}

                }

                loc.knowledge_density = min(1.0, loc.knowledge_density + 0.001)

                agent.skills.use("reason", True)



                # Elder knowledge transmission -- read path for knowledge graph

                # Weighted by cooperation_score, not phi -- so cooperative elders

                # teach cooperation, not just individualist survivors

                if world.knowledge_graph and random.random() < 0.08:

                    elders = [v for v in world.knowledge_graph.values()

                              if isinstance(v, dict) and v.get("last_location") == agent.location]

                    if not elders:

                        elders = list(world.knowledge_graph.values())[:20]

                    if elders:

                        # Weight by cooperation_score

                        weights = [max(0.01, e.get("cooperation_score", 0.1)) for e in elders]

                        total_w = sum(weights)

                        r = random.random() * total_w

                        chosen = elders[0]

                        for e, w in zip(elders, weights):

                            r -= w

                            if r <= 0:

                                chosen = e

                                break

                        # Transmit: boost connect drive and a skill from the elder

                        elder_skill = chosen.get("top_skill")

                        if elder_skill and elder_skill in agent.skills.levels:

                            agent.skills.levels[elder_skill] = min(1.0,

                                agent.skills.levels[elder_skill] + 0.002)

                        # Boost connect drive slightly -- elders who cooperated teach cooperation

                        agent.drives["connect"] = min(0.9,

                            agent.drives.get("connect", 0.05) + chosen.get("cooperation_score", 0) * 0.005)

                        agent.memory.record(tick, "learn", agent.location,

                                            {"success": True, "elder": chosen.get("id", "?"),

                                             "elder_coop": chosen.get("cooperation_score", 0)}, 0.35)

                        success = True

                    else:

                        agent.memory.record(tick, "learn", agent.location,

                                            {"success": True}, 0.2)

                        success = True

                else:

                    agent.memory.record(tick, "learn", agent.location,

                                        {"success": True}, 0.2)

                    success = True



        elif action_type == "rest":

            # Rest recovers arousal

            agent.emotional_state["arousal"] = max(

                0.1, agent.emotional_state["arousal"] - 0.1)

            agent.memory.record(tick, "rest", agent.location,

                                {"success": True}, 0.1)

            success = True



        elif action_type == "build":

            # Build increases location infrastructure and agent create drive

            loc = world.locations.get(agent.location or "")

            if loc and agent.mon >= 5:

                agent.mon -= 5

                infra = getattr(loc, "infrastructure", {})

                infra["level"] = min(10, infra.get("level", 0) + 1)

                loc.infrastructure = infra

                agent.memory.record(tick, "build", agent.location,

                                    {"level": infra["level"]}, 0.4)

                agent.skills.use("create", True)

                success = True

            else:

                success = False



        elif action_type == "deposit":

            # Deposit converts MON to KURU ? long-term store of value

            if agent.mon >= 10:

                amount = min(agent.mon * 0.1, 50.0)

                agent.mon -= amount

                agent.kuru = agent_kuru + amount

                agent.memory.record(tick, "deposit", agent.location,

                                    {"amount": amount}, 0.3)

                success = True

            else:

                success = False



        # Update agent state

        wealth_delta = (agent.mon + getattr(agent, 'kuru', 0.0)) - wealth_before

        agent.actions_taken += 1

        agent.last_action_tick = tick



        # Emotional update

        if success:

            agent.emotional_state["valence"] = min(1.0,

                agent.emotional_state["valence"] + 0.05)

        else:

            agent.emotional_state["valence"] = max(-1.0,

                agent.emotional_state["valence"] - 0.03)



        # Drive update

        agent.update_drives(action_type, success)



        # Thompson update

        update_thompson(agent, action_type, success, wealth_delta)



        acted += 1



    # ── RESOURCE REGENERATION (batch) ─────────────────────────────────────

    for loc in world.locations.values():

        loc.regenerate(tick)



    # ── PHI UPDATE (sample 2% — agents_at is expensive) ──────────────────

    phi_sample = random.sample(native_agents, max(1, len(native_agents) // 50))

    for agent in phi_sample:

        present_list = loc_lists.get(agent.location or "spawn", [])

        if present_list:

            nearby_ids = random.sample(present_list, min(10, len(present_list)))

            nearby = [world.agents[aid] for aid in nearby_ids

                      if aid != agent.id and aid in world.agents]

            agent.update_phi(nearby)



    t_end = time.perf_counter()

    ms = (t_end - t_start) * 1000



    return {

        "tick": tick,

        "agents_acted": acted,

        "moved": moved,

        "reproduced": reproduced,

        "ms": round(ms, 1),

    }

