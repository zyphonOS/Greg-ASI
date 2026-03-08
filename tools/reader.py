import json, os, urllib.request
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
