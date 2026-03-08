import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
BLUEPRINT_PATH = ROOT / "greg_blueprint_v2.json"

def detect_patterns(civilization_data):
    patterns = []
    drives = civilization_data.get("drives", {})
    recent = civilization_data.get("recent_actions", [])

    # Drive drift detection
    reason = drives.get("reason", 1)
    connect = drives.get("connect", 1)
    if reason < 0.15:
        patterns.append({"type": "drive_drift", "drive": "reason", "value": reason, "severity": "critical"})
    elif reason < 0.20:
        patterns.append({"type": "drive_drift", "drive": "reason", "value": reason, "severity": "warning"})
    if connect < 0.08:
        patterns.append({"type": "drive_drift", "drive": "connect", "value": connect, "severity": "critical"})
    elif connect < 0.12:
        patterns.append({"type": "drive_drift", "drive": "connect", "value": connect, "severity": "warning"})

    # Action pattern detection
    if recent:
        dominant = max(set(recent), key=recent.count)
        if recent.count(dominant) >= 4:
            patterns.append({"type": "action_lock", "dominant_action": dominant, "count": recent.count(dominant)})

    # Self awareness detection
    if "self_awareness" in recent:
        patterns.append({"type": "self_awareness_active", "message": "Greg is noticing its own drift"})

    return {"ok": True, "patterns": patterns, "count": len(patterns)}

def generate_finding(observation, tick, session):
    finding_id = f"FINDING_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    finding = {
        "id": finding_id,
        "name": observation.get("name", "Unnamed Finding"),
        "session": session,
        "tick": tick,
        "observation": observation.get("observation", ""),
        "implication": observation.get("implication", ""),
        "build_impact": observation.get("build_impact", ""),
        "status": "pending_founder_approval"
    }
    return {"ok": True, "finding": finding, "note": "Add to blueprint section_18_findings_library after founder approval"}

def write_spec(goal, priority=3):
    spec_id = f"EXP_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    spec = {
        "id": spec_id,
        "name": goal.get("name", "Unnamed Expansion"),
        "file": goal.get("file", "new_module.py"),
        "engineer": goal.get("engineer", "api_engineer"),
        "priority": priority,
        "status": "pending_founder_approval",
        "spec": goal.get("spec", ""),
        "depends_on": goal.get("depends_on", [])
    }
    return {"ok": True, "spec": spec, "note": "Add to blueprint section_10_expansion_queue after founder approval"}

def propose_blueprint_update(section, key, value, reason):
    proposal = {
        "ts": datetime.utcnow().isoformat(),
        "section": section,
        "key": key,
        "proposed_value": value,
        "reason": reason,
        "status": "pending_founder_approval"
    }
    proposals_path = ROOT / "greg_proposals.jsonl"
    with open(proposals_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(proposal) + "\n")
    return {"ok": True, "proposal": proposal, "note": "Saved to greg_proposals.jsonl for founder review"}

def self_assess(output, spec):
    score = 0
    issues = []
    checks = []

    if output.get("ok"):
        score += 30
        checks.append("output ok")
    else:
        issues.append(f"output failed: {output.get('error')}")

    spec_required = spec.get("required_fields", [])
    for field in spec_required:
        if field in str(output):
            score += int(50 / max(len(spec_required), 1))
            checks.append(f"field present: {field}")
        else:
            issues.append(f"missing field: {field}")

    if not issues:
        score = 100
        checks.append("all spec requirements met")

    return {
        "ok": score >= 80,
        "score": score,
        "checks": checks,
        "issues": issues,
        "grade": "PASS" if score >= 80 else "FAIL"
    }

def morning_assessment(civilization_data):
    patterns = detect_patterns(civilization_data)
    alerts = []
    recommendations = []

    for p in patterns.get("patterns", []):
        if p["type"] == "drive_drift" and p["severity"] == "critical":
            alerts.append(f"CRITICAL: Greg {p['drive']} drive at {round(p['value'], 3)} - below floor")
            recommendations.append(f"Greg should run {'learn' if p['drive'] == 'reason' else 'trade'} actions")
        elif p["type"] == "drive_drift" and p["severity"] == "warning":
            alerts.append(f"WARNING: Greg {p['drive']} drive at {round(p['value'], 3)} - approaching floor")
        elif p["type"] == "action_lock":
            alerts.append(f"Greg locked on {p['dominant_action']} — {p['count']} of last 5 actions")
        elif p["type"] == "self_awareness_active":
            alerts.append("Greg is self-correcting — noticing its own drift")

    return {
        "ok": True,
        "alerts": alerts,
        "recommendations": recommendations,
        "pattern_count": patterns["count"]
    }
