import ast, json, subprocess, urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
BLUEPRINT_PATH = ROOT / "greg_blueprint_v2.json"

GREG_PROTECTED_TICK = [
    "_force_next_action",
    "archetype"
]
GREG_PROTECTED_AGENT = [
    "self_awareness",
    "_reason_drift_flagged",
    "_connect_drift_flagged",
    "emotional_weight",
    "archetype"
]
GREG_PROTECTED = GREG_PROTECTED_TICK  # default for tick.py

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
    import urllib.request
    routes = ["/health","/api/world/state","/api/world/agents",
              "/api/world/elders","/api/world/locations",
              "/api/agent/greg_meta","/api/agent/greg_voice"]
    passed = 0
    for route in routes:
        try:
            urllib.request.urlopen("http://localhost:5000" + route, timeout=5)
            passed += 1
        except: pass
    ok = passed == len(routes)
    return {"ok": ok, "score": f"{passed}/{len(routes)}", "result": "PERFECT SCORE" if ok else "FAILING"}

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
