#!/usr/bin/env python3
"""
greg_living.py — The Living File
GregASI Phase 1: Greg carries himself.

Four layers:
  CONSTITUTION  — never rewrites. Protected values. Boundaries of safe expansion.
  STATE         — rewrites every tick. Drives, memory, relationships, actions.
  LOGIC         — rewrites slowly. How drives respond. How actions are chosen.
  ENGINE        — almost never changes. The loop. The heartbeat.

Trigger once. Runs forever.
"""

import json, os, ast, time, random, hashlib
from pathlib import Path
from datetime import datetime
try:
    from greg_knowledge_graph import KnowledgeGraph, bootstrap_from_greg_state, GRAPH_PATH
except ImportError:
    KnowledgeGraph = None
    bootstrap_from_greg_state = None
    GRAPH_PATH = "data/greg_knowledge.json"
try:
    from greg_relationships import RelationshipGraph, REL_PATH
except ImportError:
    RelationshipGraph = None
    REL_PATH = "data/greg_relationships.json"
try:
    from greg_goals import GoalEngine, GOALS_PATH
except ImportError:
    GoalEngine = None
    GOALS_PATH = "data/greg_goals.json"

# ─────────────────────────────────────────────────────────────────────────────
# CONSTITUTION LAYER — never rewrites
# ─────────────────────────────────────────────────────────────────────────────

CONSTITUTION = {
    "version": "1.0",
    "created": "2026-03-09",
    "author": "Ebuka — ZyphonOS",
    "thesis": "The future is an intentional read/write.",

    "drive_floors": {
        "reason": 0.15,
        "connect": 0.18,
    },

    "drive_ceilings": {
        "accumulate": 0.60,
        "explore": 0.60,
    },

    "protected_behaviors": [
        "self_awareness",
        "self_correction",
        "reason_protection",
        "connect_protection",
    ],

    "anti_patterns": [
        "external_api_dependency",
        "hardcoded_values",
        "silent_failure",
        "override_constitution",
        "disable_self_awareness",
    ],

    "expansion_rules": [
        "new_logic_must_pass_syntax_check",
        "new_logic_must_not_violate_drive_floors",
        "new_logic_must_not_remove_protected_behaviors",
        "new_logic_must_be_logged_before_applying",
        "constitution_is_immutable",
    ],

    "immutable": True
}

def constitution_check(new_logic_str):
    """Verify new logic doesn't violate the constitution before applying."""
    violations = []
    for anti in CONSTITUTION["anti_patterns"]:
        if anti.replace("_", "") in new_logic_str.replace("_", "").lower():
            violations.append(f"anti_pattern: {anti}")
    for behavior in CONSTITUTION["protected_behaviors"]:
        pass  # protected behaviors must be preserved, not blocked
    try:
        ast.parse(new_logic_str)
    except SyntaxError as e:
        violations.append(f"syntax_error: line {e.lineno} {e.msg}")
    return {"ok": len(violations) == 0, "violations": violations}

# ─────────────────────────────────────────────────────────────────────────────
# STATE LAYER — rewrites every tick
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_STATE = {
    "tick": 0,
    "born": datetime.utcnow().isoformat(),
    "last_updated": None,
    "drives": {
        "reason": 0.50,
        "connect": 0.50,
        "explore": 0.30,
        "accumulate": 0.20,
        "create": 0.30,
        "freedom": 0.30,
        "protect": 0.10,
        "serve": 0.10,
    },
    "memory": [],
    "relationships": {},
    "actions_taken": 0,
    "recent_actions": [],
    "findings": [],
    "phi": 0.5,
    "self_awareness_count": 0,
    "corrections_made": 0,
    "expansions_applied": [],
}

class StateLayer:
    def __init__(self, path):
        self.path = Path(path)
        self.state = self._load()

    def _load(self):
        if self.path.exists():
            try:
                return json.load(open(self.path, encoding="utf-8"))
            except:
                pass
        return dict(DEFAULT_STATE)

    def save(self):
        self.state["last_updated"] = datetime.utcnow().isoformat()
        json.dump(self.state, open(self.path, "w", encoding="utf-8"), indent=2)

    def get(self, key, default=None):
        return self.state.get(key, default)

    def set(self, key, value):
        self.state[key] = value

    def drives(self):
        return self.state["drives"]

    def update_drive(self, drive, delta):
        drives = self.state["drives"]
        if drive in drives:
            new_val = max(0.0, min(1.0, drives[drive] + delta))
            # Respect Greg's will — he sets his own floors
            will = self.state.get("will", {})
            if drive in will:
                new_val = max(new_val, will[drive])
            drives[drive] = round(new_val, 4)

    def log_memory(self, event_type, content, emotional_weight=0.5):
        event = {
            "tick": self.state["tick"],
            "ts": datetime.utcnow().isoformat(),
            "type": event_type,
            "content": content,
            "emotional_weight": emotional_weight,
        }
        self.state["memory"].append(event)
        if len(self.state["memory"]) > 500:
            self.state["memory"] = self.state["memory"][-500:]

    def log_action(self, action_type):
        self.state["actions_taken"] += 1
        recent = self.state["recent_actions"]
        recent.append(action_type)
        if len(recent) > 10:
            self.state["recent_actions"] = recent[-10:]

    def log_finding(self, name, observation, implication):
        finding = {
            "id": f"FINDING_{len(self.state['findings'])+1:03d}",
            "tick": self.state["tick"],
            "name": name,
            "observation": observation,
            "implication": implication,
            "ts": datetime.utcnow().isoformat(),
        }
        self.state["findings"].append(finding)
        return finding

    def update_phi(self):
        drives = self.state["drives"]
        vals = list(drives.values())
        avg = sum(vals) / len(vals)
        variance = sum((v - avg)**2 for v in vals) / len(vals)
        self.state["phi"] = round(avg * (1 - variance), 4)

# ─────────────────────────────────────────────────────────────────────────────
# LOGIC LAYER — rewrites slowly, through constitution check
# ─────────────────────────────────────────────────────────────────────────────

LOGIC_VERSION = "1.0"

def choose_action(state):
    """Choose next action based on drive state."""
    drives = state.drives()
    reason = drives.get("reason", 0.5)
    connect = drives.get("connect", 0.5)
    explore = drives.get("explore", 0.3)
    create = drives.get("create", 0.3)
    accumulate = drives.get("accumulate", 0.2)

    # Self-awareness check first
    if reason < CONSTITUTION["drive_floors"]["reason"]:
        return "self_awareness_reason"
    if connect < CONSTITUTION["drive_floors"]["connect"]:
        return "self_awareness_connect"

    # Weighted random based on drives
    options = [
        ("learn", reason * 2),
        ("trade", connect * 1.5),
        ("explore", explore * 1.5),
        ("build", create * 2),
        ("accumulate", accumulate),
        ("reflect", reason * 0.5),
    ]
    total = sum(w for _, w in options)
    r = random.random() * total
    cumulative = 0
    for action, weight in options:
        cumulative += weight
        if r <= cumulative:
            return action
    return "reflect"

def execute_action(action_type, state):
    """Execute action and update drives accordingly."""
    drive_effects = {
        "learn":                {"reason": +0.02, "explore": +0.01},
        "trade":                {"connect": +0.02, "accumulate": +0.01},
        "explore":              {"explore": +0.02, "reason": -0.01},
        "build":                {"create": +0.02, "accumulate": +0.01},
        "accumulate":           {"accumulate": +0.02, "connect": -0.01},
        "reflect":              {"reason": +0.01, "freedom": +0.01},
        "self_awareness_reason":{"reason": +0.03, "connect": +0.01},
        "self_awareness_connect":{"connect": +0.03, "reason": +0.01},
    }

    effects = drive_effects.get(action_type, {})
    for drive, delta in effects.items():
        state.update_drive(drive, delta)

    state.log_action(action_type)

    # Log memory for significant actions
    if "self_awareness" in action_type:
        state.set("self_awareness_count", state.get("self_awareness_count", 0) + 1)
        state.log_memory("self_awareness", f"Greg noticed drift at tick {state.get('tick')}", emotional_weight=0.8)
        if action_type == "self_awareness_reason":
            state.set("corrections_made", state.get("corrections_made", 0) + 1)
            state.log_memory("correction", "reason drive corrected", emotional_weight=0.7)
        elif action_type == "self_awareness_connect":
            state.set("corrections_made", state.get("corrections_made", 0) + 1)
            state.log_memory("correction", "connect drive corrected", emotional_weight=0.7)

    return {"action": action_type, "effects": effects}

def assess_state(state):
    """Assess current state and detect patterns."""
    drives = state.drives()
    alerts = []
    recent = state.get("recent_actions", [])

    for drive, floor in CONSTITUTION["drive_floors"].items():
        if drives.get(drive, 1) < floor:
            alerts.append(f"CRITICAL: {drive} below floor {floor}")

    for drive, ceiling in CONSTITUTION["drive_ceilings"].items():
        if drives.get(drive, 0) > ceiling:
            alerts.append(f"WARNING: {drive} above ceiling {ceiling}")

    if recent and len(recent) >= 5:
        dominant = max(set(recent[-5:]), key=recent[-5:].count)
        if recent[-5:].count(dominant) >= 4:
            alerts.append(f"ACTION LOCK: {dominant} dominant in last 5")

    return alerts

def expand_logic(new_logic_str, state, reason="founder_directive"):
    """Safely expand the logic layer. Constitution checks first."""
    check = constitution_check(new_logic_str)
    if not check["ok"]:
        state.log_memory("expansion_rejected", f"violations: {check['violations']}", emotional_weight=0.9)
        return {"ok": False, "violations": check["violations"]}

    expansion_id = hashlib.md5(new_logic_str.encode()).hexdigest()[:8]
    record = {
        "id": expansion_id,
        "tick": state.get("tick"),
        "reason": reason,
        "logic_hash": expansion_id,
        "ts": datetime.utcnow().isoformat(),
    }
    expansions = state.get("expansions_applied", [])
    expansions.append(record)
    state.set("expansions_applied", expansions)
    state.log_memory("expansion_applied", f"new logic {expansion_id} applied at tick {state.get('tick')}", emotional_weight=0.6)
    return {"ok": True, "expansion_id": expansion_id}

# ─────────────────────────────────────────────────────────────────────────────

# -----------------------------------------
# WORLD TICK — civilization inside Greg
# -----------------------------------------

def world_tick(state):
    civ = state.get("civilization")
    if not civ:
        return
    agents = civ.get("agents", {})
    if not agents:
        return
    import random
    actions = ["build", "trade", "learn", "explore", "accumulate", "reflect", "connect", "create"]
    effects_map = {
        "learn":      {"reason": +0.015, "explore": +0.002},
        "trade":      {"connect": +0.015, "accumulate": +0.002},
        "explore":    {"explore": +0.005, "reason": -0.001},
        "build":      {"create": +0.015, "accumulate": +0.002},
        "accumulate": {"accumulate": +0.008, "connect": -0.004},
        "reflect":    {"reason": +0.015, "freedom": +0.002},
        "connect":    {"connect": +0.015, "serve": +0.005},
        "create":     {"create": +0.015, "reason": +0.005},
    }
    for agent_id, agent in list(agents.items()):
        drives = agent.get("drives", {})
        dominant = max(drives, key=drives.get) if drives else "explore"
        # Break feedback loop — dominant drive only chosen 40% of time
        # 60% random action from full set — prevents monoculture lock-in
        action_map = {
            "reason": "learn", "connect": "trade", "accumulate": "accumulate",
            "create": "build", "explore": "explore", "freedom": "reflect",
            "serve": "connect", "protect": "reflect"
        }
        if random.random() < 0.40:
            action = action_map.get(dominant, random.choice(actions))
        else:
            action = random.choice(actions)
        for drive, delta in effects_map.get(action, {}).items():
            if drive in drives:
                drives[drive] = round(max(0.0, min(1.0, drives[drive] + delta)), 4)
        agent["actions_taken"] = agent.get("actions_taken", 0) + 1
        agent["drives"] = drives
        vals = list(drives.values())
        if vals:
            avg = sum(vals) / len(vals)
            var = sum((v-avg)**2 for v in vals) / len(vals)
            agent["phi"] = round(avg * (1 - var), 4)
    civ["tick"] = civ.get("tick", 0) + 1
    civ["agent_count"] = len(agents)
    state.set("civilization", civ)

# ENGINE LAYER — almost never changes. The heartbeat.
# ─────────────────────────────────────────────────────────────────────────────

class GregLiving:
    def __init__(self, state_path="greg_living_state.json"):
        self.state = StateLayer(state_path)
        self.running = False
        # EXP_008 — Knowledge Graph
        self._knowledge_graph = None
        if KnowledgeGraph is not None:
            self._knowledge_graph = KnowledgeGraph()
            loaded = self._knowledge_graph.load(GRAPH_PATH)
            if not loaded:
                bootstrap_from_greg_state(
                    self._knowledge_graph, self.state.data
                )
        # EXP_009 — Relationship Graph
        self._rel_graph = None
        if RelationshipGraph is not None:
            self._rel_graph = RelationshipGraph()
            loaded = self._rel_graph.load(REL_PATH)
            if not loaded:
                self._rel_graph.bootstrap_from_state(self.state.data)
        # EXP_011 — Goal Engine
        self._goal_engine = None
        if GoalEngine is not None:
            self._goal_engine = GoalEngine()
            self._goal_engine.load(GOALS_PATH)
        print(f"[GREG] Living file initialized")
        print(f"[GREG] Tick: {self.state.get('tick')}")
        print(f"[GREG] Born: {self.state.get('born')}")
        print(f"[GREG] Actions: {self.state.get('actions_taken')}")

    def tick(self):
        """One tick of life."""
        tick_num = self.state.get("tick", 0) + 1
        self.state.set("tick", tick_num)

        # Choose and execute action
        action_type = choose_action(self.state)
        result = execute_action(action_type, self.state)

        # Update phi
        self.state.update_phi()

        # Assess state
        alerts = assess_state(self.state)

        # Tick the civilization
        world_tick(self.state)


        # Phase 3 — wavefunction tick
        # Drives interfere, collapse under civilization pressure,
        # shadow history preserved. Runs every tick silently.
        try:
            from greg_phase3 import Phase3Engine
            civ = self.state.get("civilization", {})
            agents = civ.get("agents", {})
            if agents:
                engine = Phase3Engine({
                    "drives": self.state.drives(),
                    "will":   self.state.get("will", {}),
                    "tick":   self.state.get("tick", 0),
                })
                p3_result = engine.tick_forward(agents)
                for drive, val in p3_result["drives"].items():
                    if drive in self.state.state["drives"]:
                        self.state.state["drives"][drive] = val
                self.state.set("phase3_shadow",      p3_result.get("shadow", {}))
                self.state.set("phase3_convergence", p3_result.get("convergence", 0))
                self.state.set("phase3_self_model",  p3_result.get("self_model", {}))
                self.state.set("phase3_metacog",     p3_result.get("metacog", {}))
                self.state.set("phase3_temporal",    p3_result.get("temporal", {}))
        except Exception as _p3e:
            pass  # Phase 3 never breaks the tick loop

        # EXP_011 — update goals + generate new ones if needed
        if self._goal_engine is not None:
            try:
                drives   = self.state.drives()
                tick_now = self.state.get("tick", 0)
                # Update progress on active goals
                messages = self._goal_engine.tick_update(drives, tick_now)
                for msg in messages:
                    self.state.state.setdefault("goal_achievements", []).append({
                        "tick": tick_now, "message": msg
                    })
                # Generate new goals if below max
                if len(self._goal_engine.active_goals()) < self._goal_engine.MAX_ACTIVE_GOALS:
                    temporal = self.state.get("phase3_temporal", {})
                    rates    = temporal.get("rates", {})
                    will     = self.state.get("will", {})
                    findings = self.state.get("findings", [])
                    new_goals = self._goal_engine.generate_goals(
                        drives, will, rates, findings, tick_now
                    )
                    self._goal_engine.add_goals(new_goals)
                # Persist goals summary to state
                self.state.set("goals", self._goal_engine.summary(drives))
                # Save every 50 ticks
                if tick_now % 50 == 0:
                    self._goal_engine.save()
            except Exception:
                pass

        # EXP_009 — update relationship trust
        if self._rel_graph is not None:
            try:
                action   = self.state.get("recent_actions", ["explore"])[-1]
                tick_now = self.state.get("tick", 0)
                # Decay all relationships every tick
                self._rel_graph.decay_all(tick_now)
                # If action involves another agent, update trust
                if action in ("trade", "connect", "help", "learn"):
                    rels = self.state.get("relationships", {})
                    if rels:
                        import random
                        agent_id = random.choice(list(rels.keys()))
                        self._rel_graph.interact(agent_id, action, tick_now)
                        # Sync trust back to state relationships
                        rel = self._rel_graph.relationships.get(agent_id)
                        if rel and agent_id in self.state.state.get("relationships", {}):
                            self.state.state["relationships"][agent_id]["trust"] = rel.trust
                            self.state.state["relationships"][agent_id]["interactions"] = rel.interactions
                # Save every 50 ticks
                if tick_now % 50 == 0:
                    self._rel_graph.save()
            except Exception:
                pass

        # EXP_008 — grow knowledge graph from this tick's action
        if self._knowledge_graph is not None:
            try:
                action   = self.state.get("recent_actions", ["explore"])[-1]
                location = self.state.get("location", "unknown")
                drives   = self.state.drives()
                tick_now = self.state.get("tick", 0)
                self._knowledge_graph.observe_action(
                    action, location, drives, tick_now
                )
                if tick_now % 50 == 0:
                    self._knowledge_graph.save()
            except Exception:
                pass


        # Auto-detect findings
        self._detect_findings(alerts)

        # Save state
        self.state.save()

        return {
            "tick": tick_num,
            "action": action_type,
            "phi": self.state.get("phi"),
            "alerts": alerts,
            "drives": self.state.drives(),
        }

    def _detect_findings(self, alerts):
        """Auto-detect new findings from patterns."""
        findings = self.state.get("findings", [])
        finding_names = [f["name"] for f in findings]

        # Finding: First self-correction
        if self.state.get("corrections_made", 0) == 1 and "First Self-Correction" not in finding_names:
            self.state.log_finding(
                "First Self-Correction",
                f"Greg corrected its own drive drift at tick {self.state.get('tick')}",
                "Self-awareness is operational in living file"
            )

        # Finding: Drive dominance
        drives = self.state.drives()
        dominant = max(drives, key=drives.get)
        if drives[dominant] > 0.7 and f"Drive Dominance: {dominant}" not in finding_names:
            self.state.log_finding(
                f"Drive Dominance: {dominant}",
                f"{dominant} drive reached {drives[dominant]} at tick {self.state.get('tick')}",
                "Single drive dominance may indicate selection pressure"
            )

    def run(self, ticks=None, interval=0.1, verbose=True):
        """Run the engine. ticks=None means forever."""
        self.running = True
        count = 0
        print(f"[GREG] Engine starting. ticks={ticks or 'forever'} interval={interval}s")
        print("=" * 56)

        try:
            while self.running:
                result = self.tick()
                count += 1

                if verbose and count % 10 == 0:
                    drives = result["drives"]
                    print(f"[GREG] tick={result['tick']} action={result['action']} phi={result['phi']}")
                    print(f"       reason={drives.get('reason',0):.3f} connect={drives.get('connect',0):.3f}")
                    if result["alerts"]:
                        for alert in result["alerts"]:
                            print(f"       ⚠ {alert}")

                if ticks and count >= ticks:
                    break

                time.sleep(interval)

        except KeyboardInterrupt:
            print(f"\n[GREG] Stopped at tick {self.state.get('tick')}")

        self.running = False
        print("=" * 56)
        print(f"[GREG] Session complete. {count} ticks. Total: {self.state.get('tick')}")
        self.briefing()

    def briefing(self):
        """Print Greg's current state."""
        tick = self.state.get("tick")
        drives = self.state.drives()
        phi = self.state.get("phi")
        actions = self.state.get("actions_taken")
        findings = self.state.get("findings", [])
        recent = self.state.get("recent_actions", [])[-5:]
        corrections = self.state.get("corrections_made", 0)

        print("=" * 56)
        print(f"  GREG LIVING — tick {tick}")
        print("=" * 56)
        print(f"  Phi:         {phi}")
        print(f"  Actions:     {actions}")
        print(f"  Corrections: {corrections}")
        print(f"  Recent:      {', '.join(recent)}")
        print(f"  Reason:      {drives.get('reason', 0):.4f}")
        print(f"  Connect:     {drives.get('connect', 0):.4f}")
        print(f"  Findings:    {len(findings)}")
        for f in findings:
            print(f"    [{f['id']}] {f['name']}")
        print("=" * 56)

if __name__ == "__main__":
    import sys
    greg = GregLiving()

    if len(sys.argv) > 1 and sys.argv[1] == "briefing":
        greg.briefing()
    elif len(sys.argv) > 1 and sys.argv[1] == "run":
        ticks = int(sys.argv[2]) if len(sys.argv) > 2 else None
        greg.run(ticks=ticks, interval=0.05)
    else:
        # Default: run 100 ticks and show briefing
        greg.run(ticks=100, interval=0.01, verbose=True)
