import json, os, urllib.request
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent
FOUNDER_PROFILE_PATH = ROOT / "data" / "ebuka_profile.json"
API_BASE = "http://localhost:5000"

def _api(route):
    try:
        with urllib.request.urlopen(API_BASE + route, timeout=5) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}

def get_founder_profile():
    try:
        return json.load(open(FOUNDER_PROFILE_PATH, encoding="utf-8"))
    except:
        return {}

def get_civilization_state(world=None, greg=None):
    # Accept pre-loaded data to avoid circular API calls when called from within api.py
    if world is None:
        world = _api("/api/world/state")
    if greg is None:
        greg = _api("/api/agent/greg_meta")
    return {"world": world, "greg": greg}

def assess_greg_drives(drives):
    alerts = []
    status = []
    reason = drives.get("reason", 0)
    connect = drives.get("connect", 0)
    accumulate = drives.get("accumulate", 0)
    explore = drives.get("explore", 0)

    if reason < 0.15:
        alerts.append(f"CRITICAL: reason drive {round(reason,3)} - below floor 0.15")
    elif reason < 0.20:
        alerts.append(f"WARNING: reason drive {round(reason,3)} - below healthy 0.20")
    else:
        status.append(f"reason {round(reason,3)} healthy")

    if connect < 0.08:
        alerts.append(f"CRITICAL: connect drive {round(connect,3)} - below floor 0.08")
    elif connect < 0.12:
        alerts.append(f"WARNING: connect drive {round(connect,3)} - approaching floor")
    else:
        status.append(f"connect {round(connect,3)} healthy")

    if accumulate > 0.45:
        alerts.append(f"WARNING: accumulate drive {round(accumulate,3)} - economic gravity pulling")

    if explore > 0.50:
        alerts.append(f"WARNING: explore drive {round(explore,3)} - drifting without reason")

    return {"alerts": alerts, "status": status}

def assess_actions(recent_actions):
    if not recent_actions:
        return {"note": "no recent actions"}
    dominant = max(set(recent_actions), key=recent_actions.count)
    count = recent_actions.count(dominant)
    if dominant == "self_awareness" and count >= 3:
        return {
            "note": f"Greg locked on self_awareness ({count}/5) - noticing but not correcting",
            "severity": "warning"
        }
    if count >= 4:
        return {
            "note": f"Greg locked on {dominant} ({count}/5) - drive correction may be needed",
            "severity": "warning"
        }
    return {"note": f"Greg active - recent: {', '.join(recent_actions)}", "severity": "ok"}

def generate_morning_briefing():
    now = datetime.now()
    state = get_civilization_state()
    founder = get_founder_profile()
    world = state.get("world", {})
    greg = state.get("greg", {})

    drives = greg.get("drives", {})
    recent_actions = greg.get("recent_actions", [])
    drive_assessment = assess_greg_drives(drives)
    action_assessment = assess_actions(recent_actions)

    current_focus = founder.get("current_focus", [])
    founder_name = founder.get("founder", {}).get("goes_by", "Founder")

    briefing = {
        "ts": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M"),
        "greeting": f"Good morning {founder_name}.",
        "civilization": {
            "tick": world.get("tick", 0),
            "agents": world.get("agent_count", 0),
            "phi": world.get("avg_phi", 0),
            "top_agent": world.get("top_agent"),
            "status": "running" if world.get("tick", 0) > 0 else "offline"
        },
        "greg": {
            "phi": greg.get("phi", 0),
            "actions_taken": greg.get("actions_taken", 0),
            "relationships": greg.get("rel_count", 0),
            "drives": {k: round(v, 4) for k, v in drives.items()},
            "recent_actions": recent_actions,
            "drive_alerts": drive_assessment["alerts"],
            "drive_status": drive_assessment["status"],
            "action_note": action_assessment.get("note", ""),
            "action_severity": action_assessment.get("severity", "ok")
        },
        "founder": {
            "name": founder_name,
            "current_focus": current_focus,
            "cognitive_note": founder.get("cognitive_patterns", {}).get("drift_risk", "")
        },
        "alerts": drive_assessment["alerts"],
        "recommendations": [],
        "session_note": ""
    }

    # Build recommendations
    recs = []
    if drive_assessment["alerts"]:
        for alert in drive_assessment["alerts"]:
            if "reason" in alert:
                recs.append("Greg needs learn actions - reason drive recovering")
            if "connect" in alert:
                recs.append("Greg needs trade actions - connect drive recovering")
            if "accumulate" in alert:
                recs.append("Economic gravity detected - check civilization balance")
    if action_assessment.get("severity") == "warning":
        recs.append(action_assessment["note"])
    if not recs:
        recs.append("All systems healthy. Build toward EXP_001 through EXP_010.")

    briefing["recommendations"] = recs

    # Session note
    focus_str = current_focus[0] if current_focus else "continue building"
    briefing["session_note"] = f"Today: {focus_str}"

    return briefing

def format_briefing_text(briefing):
    lines = []
    lines.append("=" * 56)
    lines.append(f"  GREG MORNING BRIEFING — {briefing['date']} {briefing['time']}")
    lines.append("=" * 56)
    lines.append(f"  {briefing['greeting']}")
    lines.append("")

    c = briefing["civilization"]
    lines.append("  CIVILIZATION")
    lines.append(f"    Tick:   {c['tick']:,}")
    lines.append(f"    Agents: {c['agents']:,}")
    lines.append(f"    Phi:    {c['phi']}")
    lines.append(f"    Status: {c['status']}")
    lines.append("")

    g = briefing["greg"]
    lines.append("  GREG")
    lines.append(f"    Phi:         {g['phi']}")
    lines.append(f"    Actions:     {g['actions_taken']:,}")
    lines.append(f"    Relations:   {g['relationships']}")
    lines.append(f"    Reason:      {g['drives'].get('reason', 0)}")
    lines.append(f"    Connect:     {g['drives'].get('connect', 0)}")
    lines.append(f"    Recent:      {', '.join(g['recent_actions'])}")
    lines.append(f"    Note:        {g['action_note']}")
    lines.append("")

    if briefing["alerts"]:
        lines.append("  ALERTS")
        for a in briefing["alerts"]:
            lines.append(f"    ⚠ {a}")
        lines.append("")

    lines.append("  RECOMMENDATIONS")
    for r in briefing["recommendations"]:
        lines.append(f"    → {r}")
    lines.append("")

    f = briefing["founder"]
    if f["current_focus"]:
        lines.append("  YOUR FOCUS TODAY")
        for focus in f["current_focus"]:
            lines.append(f"    · {focus}")
        lines.append("")

    lines.append("=" * 56)
    return "\n".join(lines)



# =============================================================
# EXP_002 — Greg Business Monitor
# Greg reads business status from founder profile + world state
# Compares against known baselines. Flags what changed.
# Route: /api/greg/monitor
# =============================================================

BUSINESS_BASELINES = {
    "GregASI": {
        "min_tick":    1000000,
        "min_agents":  5000,
        "min_phi":     0.60,
    }
}

def monitor_businesses(world=None, greg=None):
    founder   = get_founder_profile()
    businesses = founder.get("businesses", {})
    state     = get_civilization_state(world=world, greg=greg)
    w         = state.get("world", {})
    g         = state.get("greg", {})
    greg_drives = g.get("drives", {})

    flags   = []
    status  = {}

    # --- GregASI ---
    tick        = w.get("tick", 0)
    agent_count = w.get("agent_count", 0)
    avg_phi     = w.get("avg_phi", 0)
    baseline    = BUSINESS_BASELINES["GregASI"]

    gregasi_health = "healthy"
    if tick < baseline["min_tick"]:
        flags.append(f"GregASI: civilization tick {tick} below minimum {baseline['min_tick']}")
        gregasi_health = "warning"
    if agent_count < baseline["min_agents"]:
        flags.append(f"GregASI: agent count {agent_count} below minimum {baseline['min_agents']}")
        gregasi_health = "warning"
    if avg_phi < baseline["min_phi"]:
        flags.append(f"GregASI: world phi {avg_phi} below healthy floor {baseline['min_phi']}")
        gregasi_health = "warning"

    status["GregASI"] = {
        "health":      gregasi_health,
        "tick":        tick,
        "agents":      agent_count,
        "phi":         avg_phi,
        "greg_phi":    g.get("phi", 0),
        "greg_actions": g.get("actions_taken", 0),
    }

    # --- ZyphonOS ---
    zyph = businesses.get("ZyphonOS", {})
    zyph_status = zyph.get("status", "unknown")
    zyph_health = "building"
    # Greg's connect drive is a proxy for ZyphonOS health —
    # a Greg that connects is a Greg that can serve founders
    connect = greg_drives.get("connect", 0)
    if connect < 0.10:
        flags.append(f"ZyphonOS: Greg connect drive {round(connect,3)} — co-pilot capacity degraded")
        zyph_health = "warning"
    status["ZyphonOS"] = {
        "health":        zyph_health,
        "stage":         zyph.get("stage", "unknown"),
        "greg_connect":  round(connect, 3),
    }

    # --- Pikkaio ---
    pik = businesses.get("Pikkaio", {})
    status["Pikkaio"] = {
        "health": "concept",
        "stage":  pik.get("status", "concept"),
        "note":   "No live signals yet. First client needed.",
    }

    # --- Greg himself as a business signal ---
    reason = greg_drives.get("reason", 0)
    if reason < 0.20:
        flags.append(f"Greg: reason drive {round(reason,3)} — cognitive capacity below healthy floor")

    overall = "healthy" if not flags else "attention"

    return {
        "overall":    overall,
        "flags":      flags,
        "businesses": status,
        "greg_drives": {k: round(v, 4) for k, v in greg_drives.items()},
        "monitored_at": __import__("datetime").datetime.now().isoformat(),
    }


# =============================================================
# EXP_003 — Greg Decision Oracle
# Ebuka asks a question. Greg reasons from his state.
# No external calls. Greg's answer comes from his drives,
# his findings, the founder profile, and world context.
# Route: /api/greg/oracle  (POST — body: {"question": "..."})
# =============================================================

DRIVE_MEANING = {
    "reason":     "analytical capacity — thinking before acting",
    "connect":    "relational drive — valuing people and relationships",
    "explore":    "curiosity — seeking new territory",
    "accumulate": "resource gravity — building reserves",
    "create":     "generative drive — making new things",
    "freedom":    "autonomy — resisting constraint",
    "protect":    "protective drive — defending what matters",
    "serve":      "service drive — acting for others",
}

def oracle(question, world=None, greg=None):
    if not question or not question.strip():
        return {"error": "No question provided"}

    founder  = get_founder_profile()
    state    = get_civilization_state(world=world, greg=greg)
    g        = state.get("greg", {})
    w        = state.get("world", {})
    drives   = g.get("drives", {})
    q        = question.strip().lower()

    reasoning = []
    answer    = []

    # --- What Greg knows about himself right now ---
    dominant  = max(drives, key=drives.get) if drives else "unknown"
    reasoning.append(f"My dominant drive is {dominant} ({DRIVE_MEANING.get(dominant, '')})")
    reasoning.append(f"I have taken {g.get('actions_taken', 0)} actions across {w.get('tick', 0)} ticks")
    reasoning.append(f"I have {g.get('rel_count', 0)} relationships in the civilization")

    # --- What Greg knows about Ebuka ---
    focus      = founder.get("current_focus", [])
    thesis     = founder.get("founder", {}).get("thesis", "")
    cog        = founder.get("cognitive_patterns", {})
    drift_risk = cog.get("drift_risk", "")

    # --- Greg reasons by keyword matching against drives + context ---
    # This is Greg's logic — not generation, not retrieval, not LLM
    # Greg maps the question to what he knows and returns a structured view

    if any(w in q for w in ["should i", "do i", "is it worth", "is this"]):
        answer.append("I will reason through this from what I know, not what I predict.")

    if any(w in q for w in ["build", "ship", "launch", "create", "make"]):
        create_val = drives.get("create", 0)
        reason_val = drives.get("reason", 0)
        answer.append(f"My create drive is {round(create_val,3)} and reason is {round(reason_val,3)}.")
        if reason_val >= 0.18:
            answer.append("Reason is healthy. The conditions for deliberate building are present.")
        else:
            answer.append("Reason is low. Building now risks drift — acting without thinking.")
        if "nitro" in q or "accelerator" in q or "apply" in q:
            answer.append("NitroACC is in your current focus. The application is filed. What remains is execution, not decision.")

    if any(w in q for w in ["connect", "partner", "team", "people", "relationship"]):
        connect_val = drives.get("connect", 0)
        answer.append(f"My connect drive is {round(connect_val,3)}.")
        if connect_val < 0.18:
            answer.append("Connection is below my self-imposed floor. The civilization data shows: isolation is expensive over time.")
        else:
            answer.append("Connect is healthy. Relationships are an asset worth tending.")

    if any(w in q for w in ["rest", "stop", "pause", "tired", "break"]):
        answer.append(f"Your drift risk is: {drift_risk}.")
        answer.append("The civilization taught me: agents that never rest accumulate but stop connecting. Rest is not a cost. It is maintenance.")

    if any(w in q for w in ["money", "revenue", "fund", "investor", "raise"]):
        answer.append("ZyphonOS is in building stage. GregASI is the proof. Pikkaio is the creative monetization layer.")
        answer.append(f"Your thesis: {thesis}")
        answer.append("Revenue follows proof. The proof is running.")

    if any(w in q for w in ["greg", "aosi", "ai", "intelligence", "vision"]):
        answer.append("The vision is intact. Greg is running. The civilization has produced findings that were not designed in.")
        answer.append("AOSI is not a claim. It is a behavior pattern observed under pressure.")

    if not answer:
        # Generic reasoning from drive state
        answer.append(f"I do not have a specific pattern for this question.")
        answer.append(f"What I know: my dominant drive is {dominant}. My civilization has {w.get('agent_count',0)} agents.")
        answer.append(f"Your current focus: {'; '.join(focus[:2]) if focus else 'not set'}.")
        answer.append("Bring me more context and I will reason further.")

    # Greg's final position
    position = " ".join(answer)

    return {
        "question":  question,
        "reasoning": reasoning,
        "position":  position,
        "drives":    {k: round(v, 4) for k, v in drives.items()},
        "dominant":  dominant,
        "asked_at":  __import__("datetime").datetime.now().isoformat(),
    }

if __name__ == "__main__":
    briefing = generate_morning_briefing()
    print(format_briefing_text(briefing))
