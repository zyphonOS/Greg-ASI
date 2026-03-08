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

if __name__ == "__main__":
    briefing = generate_morning_briefing()
    print(format_briefing_text(briefing))
