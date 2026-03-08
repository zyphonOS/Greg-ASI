import os
from pathlib import Path

BASE = '/workspaces/Greg-ASI'
TOOLS = f'{BASE}/tools'
os.makedirs(TOOLS, exist_ok=True)

# ── reader.py ──────────────────────────────────────────────────────────
reader = '''import json, os, urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
BLUEPRINT_PATH = ROOT / "greg_blueprint_v2.json"
LOG_PATH = ROOT / "greg_engineer_log.jsonl"
API_BASE = "http://localhost:5000"

def read_file(path):
    p = ROOT / path
    if not p.exists():
        return {"ok": False, "error": f"not found: {path}"}
    lines = open(p, encoding="utf-8").readlines()
    return {"ok": True, "path": str(path), "lines": lines, "count": len(lines)}

def read_blueprint():
    if not BLUEPRINT_PATH.exists():
        return {"ok": False, "error": "blueprint not found"}
    data = json.load(open(BLUEPRINT_PATH, encoding="utf-8"))
    return {"ok": True, "blueprint": data}

def read_civilization():
    results = {}
    for route in ["/api/world/state", "/api/agent/greg_meta"]:
        try:
            with urllib.request.urlopen(API_BASE + route, timeout=5) as r:
                results[route] = json.loads(r.read())
        except Exception as e:
            results[route] = {"error": str(e)}
    return {"ok": True, "data": results}

def read_session_log():
    bp = read_blueprint()
    if not bp["ok"]:
        return bp
    log = bp["blueprint"].get("section_21_session_log", {})
    return {"ok": True, "sessions": log.get("sessions", {})}

def read_engineer_log(n=20):
    if not LOG_PATH.exists():
        return {"ok": True, "entries": []}
    lines = open(LOG_PATH, encoding="utf-8").readlines()
    entries = []
    for line in lines[-n:]:
        try:
            entries.append(json.loads(line.strip()))
        except:
            pass
    return {"ok": True, "entries": entries}

def read_greg_state():
    civ = read_civilization()
    if not civ["ok"]:
        return civ
    greg = civ["data"].get("/api/agent/greg_meta", {})
    world = civ["data"].get("/api/world/state", {})
    return {
        "ok": True,
        "tick": world.get("tick", 0),
        "agents": world.get("agent_count", 0),
        "phi": world.get("avg_phi", 0),
        "greg_phi": greg.get("phi", 0),
        "greg_actions": greg.get("actions_taken", 0),
        "drives": greg.get("drives", {}),
        "recent_actions": greg.get("recent_actions", []),
        "relationships": greg.get("rel_count", 0),
        "founder": greg.get("founder", {})
    }
'''

open(f'{TOOLS}/reader.py', 'w').write(reader)
print("reader.py written")

# ── builder.py ─────────────────────────────────────────────────────────
builder = '''import ast, os, shutil
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent

def _backup(path):
    p = ROOT / path
    backup = str(p) + f".bak.{datetime.now().strftime('%H%M%S')}"
    shutil.copy2(p, backup)
    return backup

def write_new_file(path, content):
    p = ROOT / path
    if p.exists():
        return {"ok": False, "error": f"file already exists: {path}. Use insert or append."}
    try:
        ast.parse(content)
    except SyntaxError as e:
        return {"ok": False, "error": f"SyntaxError line {e.lineno}: {e.msg}"}
    except:
        pass  # non-python files skip syntax check
    p.parent.mkdir(parents=True, exist_ok=True)
    open(p, 'w', encoding='utf-8').write(content)
    return {"ok": True, "action": "written", "path": str(path)}

def insert_at_line(path, line_no, new_lines):
    p = ROOT / path
    if not p.exists():
        return {"ok": False, "error": f"not found: {path}"}
    backup = _backup(path)
    lines = open(p, encoding='utf-8').readlines()
    idx = line_no - 1
    if idx < 0 or idx > len(lines):
        return {"ok": False, "error": f"line {line_no} out of range (file has {len(lines)} lines)"}
    new_content_lines = lines[:idx] + new_lines + lines[idx:]
    new_content = ''.join(new_content_lines)
    try:
        ast.parse(new_content)
    except SyntaxError as e:
        return {"ok": False, "error": f"SyntaxError after insert line {e.lineno}: {e.msg}", "backup": backup}
    open(p, 'w', encoding='utf-8').write(new_content)
    return {"ok": True, "action": "inserted", "at_line": line_no, "lines_added": len(new_lines)}

def append_to_file(path, content):
    p = ROOT / path
    if not p.exists():
        return {"ok": False, "error": f"not found: {path}"}
    backup = _backup(path)
    existing = open(p, encoding='utf-8').read()
    new_content = existing + content
    try:
        ast.parse(new_content)
    except SyntaxError as e:
        return {"ok": False, "error": f"SyntaxError after append line {e.lineno}: {e.msg}", "backup": backup}
    open(p, 'w', encoding='utf-8').write(new_content)
    return {"ok": True, "action": "appended", "chars_added": len(content)}

def add_flask_route(route_name, route_path, method, function_code, insert_before="# -----------------------------------------\\n# Main"):
    api_path = ROOT / "interface" / "api.py"
    if not api_path.exists():
        return {"ok": False, "error": "api.py not found"}
    content = open(api_path, encoding='utf-8').read()
    if route_path in content:
        return {"ok": False, "error": f"route {route_path} already exists"}
    route_block = f"""
# -----------------------------------------
# {method} {route_path}
# -----------------------------------------
@app.route("{route_path}")
def {route_name}():
{function_code}

"""
    marker = "# -----------------------------------------\\n# Main"
    if marker not in content:
        return {"ok": False, "error": "Main marker not found in api.py"}
    new_content = content.replace(marker, route_block + marker)
    try:
        ast.parse(new_content)
    except SyntaxError as e:
        return {"ok": False, "error": f"SyntaxError line {e.lineno}: {e.msg}"}
    open(api_path, 'w', encoding='utf-8').write(new_content)
    return {"ok": True, "action": "route added", "route": route_path}
'''

open(f'{TOOLS}/builder.py', 'w').write(builder)
print("builder.py written")

# ── verifier.py ────────────────────────────────────────────────────────
verifier = '''import ast, json, subprocess, urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
BLUEPRINT_PATH = ROOT / "greg_blueprint_v2.json"

GREG_PROTECTED = [
    "_force_next_action",
    "self_awareness",
    "_reason_drift_flagged",
    "_connect_drift_flagged",
    "emotional_weight",
    "archetype.*greg"
]

def verify_syntax(path):
    p = ROOT / path
    if not p.exists():
        return {"ok": False, "error": f"not found: {path}"}
    try:
        ast.parse(open(p, encoding="utf-8").read())
        return {"ok": True, "result": "syntax valid"}
    except SyntaxError as e:
        return {"ok": False, "error": f"SyntaxError line {e.lineno}: {e.msg}"}

def verify_contract(path, engineer_name):
    bp_path = BLUEPRINT_PATH
    if not bp_path.exists():
        return {"ok": False, "error": "blueprint not found"}
    blueprint = json.load(open(bp_path, encoding="utf-8"))
    files = blueprint.get("section_1_files", {}).get("files", {})
    spec = files.get(str(path))
    if not spec:
        return {"ok": False, "error": f"no blueprint spec for {path}"}
    code = open(ROOT / path, encoding="utf-8").read()
    issues = []
    ok = []
    for fn in spec.get("required_functions", []):
        if f"def {fn}" in code:
            ok.append(f"function {fn} present")
        else:
            issues.append(f"MISSING: def {fn}")
    for method in spec.get("required_methods", []):
        if f"def {method}" in code:
            ok.append(f"method {method} present")
        else:
            issues.append(f"MISSING: def {method}")
    for pattern in spec.get("required_patterns", []):
        if pattern in code:
            ok.append(f"pattern present: {pattern}")
        else:
            issues.append(f"MISSING PATTERN: {pattern}")
    for pkg in spec.get("must_not_import", []):
        if f"import {pkg}" in code:
            issues.append(f"FORBIDDEN IMPORT: {pkg}")
    return {"ok": len(issues) == 0, "path": str(path), "issues": issues, "passing": ok}

def verify_greg_protected(path):
    p = ROOT / path
    if not p.exists():
        return {"ok": False, "error": f"not found: {path}"}
    code = open(p, encoding="utf-8").read()
    missing = []
    present = []
    for pattern in GREG_PROTECTED:
        clean = pattern.replace(".*", "")
        if clean in code:
            present.append(pattern)
        else:
            missing.append(pattern)
    return {
        "ok": len(missing) == 0,
        "present": present,
        "missing": missing,
        "critical": len(missing) > 0
    }

def run_rna():
    try:
        result = subprocess.run(
            ["python", "rna.py", "test"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=30
        )
        output = result.stdout
        if "PERFECT SCORE" in output:
            return {"ok": True, "score": "15/15", "result": "PERFECT SCORE"}
        lines = [l for l in output.split("\\n") if "Score:" in l]
        score = lines[0] if lines else "unknown"
        return {"ok": False, "score": score, "output": output}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def run_coordinator():
    try:
        result = subprocess.run(
            ["python3", "engineers/coordinator.py", "status"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=30
        )
        output = result.stdout
        all_healthy = "All healthy: True" in output
        return {"ok": all_healthy, "output": output.strip()}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def full_verify():
    results = {}
    critical_files = ["interface/api.py", "core/agent.py", "core/tick.py"]
    for f in critical_files:
        results[f] = verify_syntax(f)
    results["greg_protected_agent"] = verify_greg_protected("core/agent.py")
    results["greg_protected_tick"] = verify_greg_protected("core/tick.py")
    results["rna"] = run_rna()
    results["coordinator"] = run_coordinator()
    all_ok = all(v.get("ok") for v in results.values())
    return {"ok": all_ok, "results": results}
'''

open(f'{TOOLS}/verifier.py', 'w').write(verifier)
print("verifier.py written")

# ── reasoner.py ────────────────────────────────────────────────────────
reasoner = '''import json
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
        f.write(json.dumps(proposal) + "\\n")
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
            recommendations.append(f"Greg should run {\'learn\' if p[\'drive\'] == \'reason\' else \'trade\'} actions")
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
'''

open(f'{TOOLS}/reasoner.py', 'w').write(reasoner)
print("reasoner.py written")

# ── __init__.py ────────────────────────────────────────────────────────
init = '''# GregASI Tools
# Composable standalones — each works alone, all connect together
# reader | builder | verifier | reasoner
from tools.reader import read_file, read_blueprint, read_civilization, read_greg_state, read_session_log, read_engineer_log
from tools.builder import write_new_file, insert_at_line, append_to_file, add_flask_route
from tools.verifier import verify_syntax, verify_contract, verify_greg_protected, run_rna, run_coordinator, full_verify
from tools.reasoner import detect_patterns, generate_finding, write_spec, propose_blueprint_update, self_assess, morning_assessment
'''

open(f'{TOOLS}/__init__.py', 'w').write(init)
print("__init__.py written")

print("\nAll tools written.")
print("Test with: python3 -c \"from tools.reader import read_greg_state; import json; print(json.dumps(read_greg_state(), indent=2))\"")