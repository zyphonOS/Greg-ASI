import os, json

BASE = '/workspaces/Greg-ASI'
ENG = f'{BASE}/engineers'
os.makedirs(ENG, exist_ok=True)

# ── BASE ENGINEER ──────────────────────────────────────────────────────
base = '''import ast, json, os, sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
BLUEPRINT_PATH = ROOT / "greg_blueprint_v2.json"
LOG_PATH = ROOT / "greg_engineer_log.jsonl"

def load_blueprint():
    with open(BLUEPRINT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def log_action(engineer, action, file, result, detail=""):
    entry = {
        "ts": datetime.utcnow().isoformat(),
        "engineer": engineer,
        "action": action,
        "file": file,
        "result": result,
        "detail": detail
    }
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\\n")

class BaseEngineer:
    name = "base"
    owned_files = []
    forbidden_files = ["greg_blueprint_v2.json", "greg_blueprint.json"]

    def __init__(self):
        self.blueprint = load_blueprint()
        self.issues = []
        self.actions = []

    def can_touch(self, filepath):
        fp = str(filepath)
        for forbidden in self.forbidden_files:
            if forbidden in fp:
                return False, f"FORBIDDEN: {forbidden} is read-only"
        for owned in self.owned_files:
            if owned in fp:
                return True, "ok"
        return False, f"NOT OWNED: {self.name} cannot touch {fp}"

    def verify_syntax(self, filepath):
        try:
            code = open(filepath, encoding="utf-8").read()
            ast.parse(code)
            return True, "syntax ok"
        except SyntaxError as e:
            return False, f"SyntaxError line {e.lineno}: {e.msg}"
        except Exception as e:
            return False, str(e)

    def status(self):
        raise NotImplementedError

    def fix(self):
        raise NotImplementedError

    def expand(self, spec):
        raise NotImplementedError

    def report(self):
        return {
            "engineer": self.name,
            "issues": self.issues,
            "actions": self.actions,
            "owned_files": self.owned_files
        }

    def run_cli(self, cmd):
        if cmd == "status":
            r = self.status()
            print(json.dumps(r, indent=2))
        elif cmd == "fix":
            r = self.fix()
            print(json.dumps(r, indent=2))
        elif cmd == "report":
            print(json.dumps(self.report(), indent=2))
        else:
            print(f"Unknown command: {cmd}. Use: status | fix | report")
'''

with open(f'{ENG}/base_engineer.py', 'w') as f:
    f.write(base)
print("base_engineer.py written")

# ── __init__.py ────────────────────────────────────────────────────────
with open(f'{ENG}/__init__.py', 'w') as f:
    f.write('# GregASI Engineers\\n')
print("__init__.py written")

# ── API ENGINEER ───────────────────────────────────────────────────────
api_eng = '''import sys, json, ast
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from engineers.base_engineer import BaseEngineer, log_action, ROOT

REQUIRED_ROUTES = [
    "/health", "/api/world/state", "/api/world/agents",
    "/api/world/elders", "/api/world/locations",
    "/api/agent/greg_meta", "/api/agent/greg_voice",
    "/api/founder/profile", "/api/founder/update"
]
REQUIRED_FUNCTIONS = ["get_world", "get_founder_profile", "build_greg_voice"]
FORBIDDEN_IMPORTS = ["anthropic", "openai"]

class ApiEngineer(BaseEngineer):
    name = "api_engineer"
    owned_files = ["interface/api.py", "interface/__init__.py"]

    def status(self):
        api_path = ROOT / "interface" / "api.py"
        issues = []
        ok = []

        # Syntax check
        valid, msg = self.verify_syntax(api_path)
        if valid:
            ok.append("syntax valid")
        else:
            issues.append(msg)

        code = open(api_path, encoding="utf-8").read()

        # Route check
        for route in REQUIRED_ROUTES:
            if route in code:
                ok.append(f"route {route}")
            else:
                issues.append(f"MISSING ROUTE: {route}")

        # Function check
        for fn in REQUIRED_FUNCTIONS:
            if f"def {fn}" in code:
                ok.append(f"function {fn}")
            else:
                issues.append(f"MISSING FUNCTION: {fn}")

        # Forbidden imports
        for pkg in FORBIDDEN_IMPORTS:
            if f"import {pkg}" in code:
                issues.append(f"FORBIDDEN IMPORT: {pkg}")

        # Greg voice local check
        if "build_greg_voice" in code and "anthropic" not in code:
            ok.append("greg_voice uses local function")
        else:
            issues.append("greg_voice may be calling external API")

        log_action(self.name, "status", "interface/api.py",
                   "issues" if issues else "healthy", str(issues))

        return {
            "engineer": self.name,
            "file": "interface/api.py",
            "healthy": len(issues) == 0,
            "ok": ok,
            "issues": issues
        }

    def fix(self):
        status = self.status()
        if status["healthy"]:
            return {"result": "already healthy", "actions": []}
        return {"result": "manual fix required", "issues": status["issues"],
                "note": "api_engineer detects but does not auto-patch — use rna.py fix"}

    def expand(self, spec):
        return {"result": "expansion queued", "spec": spec,
                "note": "New routes must be added to new files first per blueprint section_19"}

if __name__ == "__main__":
    eng = ApiEngineer()
    eng.run_cli(sys.argv[1] if len(sys.argv) > 1 else "status")
'''

with open(f'{ENG}/api_engineer.py', 'w') as f:
    f.write(api_eng)
print("api_engineer.py written")

# ── TICK ENGINEER ──────────────────────────────────────────────────────
tick_eng = '''import sys, json, ast
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from engineers.base_engineer import BaseEngineer, log_action, ROOT

REQUIRED_FUNCTIONS = ["run_tick", "batch_thompson", "batch_ml_predict", "thompson_choose"]
REQUIRED_PATTERNS = ["_force_next_action", "archetype.*greg", "self_awareness"]

class TickEngineer(BaseEngineer):
    name = "tick_engineer"
    owned_files = ["core/tick.py", "ml/__init__.py"]

    def status(self):
        tick_path = ROOT / "core" / "tick.py"
        issues = []
        ok = []

        valid, msg = self.verify_syntax(tick_path)
        if valid:
            ok.append("syntax valid")
        else:
            issues.append(msg)

        code = open(tick_path, encoding="utf-8").read()

        for fn in REQUIRED_FUNCTIONS:
            if f"def {fn}" in code:
                ok.append(f"function {fn}")
            else:
                issues.append(f"MISSING FUNCTION: {fn}")

        if "_force_next_action" in code:
            ok.append("greg force action override present")
        else:
            issues.append("CRITICAL: greg force action override missing")

        if "self_awareness" in code or "archetype" in code:
            ok.append("greg archetype check present")
        else:
            issues.append("CRITICAL: greg archetype check missing")

        log_action(self.name, "status", "core/tick.py",
                   "issues" if issues else "healthy", str(issues))

        return {
            "engineer": self.name,
            "file": "core/tick.py",
            "healthy": len(issues) == 0,
            "ok": ok,
            "issues": issues
        }

    def fix(self):
        status = self.status()
        if status["healthy"]:
            return {"result": "already healthy", "actions": []}
        return {"result": "manual fix required", "issues": status["issues"]}

    def expand(self, spec):
        return {"result": "expansion queued", "spec": spec}

if __name__ == "__main__":
    eng = TickEngineer()
    eng.run_cli(sys.argv[1] if len(sys.argv) > 1 else "status")
'''

with open(f'{ENG}/tick_engineer.py', 'w') as f:
    f.write(tick_eng)
print("tick_engineer.py written")

# ── AGENT ENGINEER ─────────────────────────────────────────────────────
agent_eng = '''import sys, json, ast
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from engineers.base_engineer import BaseEngineer, log_action, ROOT

REQUIRED_METHODS = ["update_drives", "update_phi", "meet", "to_dict", "from_dict"]
PROTECTED_PATTERNS = ["self_awareness", "_reason_drift_flagged", "_force_next_action", "emotional_weight"]

class AgentEngineer(BaseEngineer):
    name = "agent_engineer"
    owned_files = ["core/agent.py", "mind/language.py"]

    def status(self):
        agent_path = ROOT / "core" / "agent.py"
        issues = []
        ok = []

        valid, msg = self.verify_syntax(agent_path)
        if valid:
            ok.append("syntax valid")
        else:
            issues.append(msg)

        code = open(agent_path, encoding="utf-8").read()

        for method in REQUIRED_METHODS:
            if f"def {method}" in code:
                ok.append(f"method {method}")
            else:
                issues.append(f"MISSING METHOD: {method}")

        for pattern in PROTECTED_PATTERNS:
            if pattern in code:
                ok.append(f"protected pattern present: {pattern}")
            else:
                issues.append(f"CRITICAL: protected pattern missing: {pattern}")

        log_action(self.name, "status", "core/agent.py",
                   "issues" if issues else "healthy", str(issues))

        return {
            "engineer": self.name,
            "file": "core/agent.py",
            "healthy": len(issues) == 0,
            "ok": ok,
            "issues": issues
        }

    def fix(self):
        status = self.status()
        if status["healthy"]:
            return {"result": "already healthy", "actions": []}
        return {"result": "manual fix required", "issues": status["issues"]}

    def expand(self, spec):
        return {"result": "expansion queued", "spec": spec}

if __name__ == "__main__":
    eng = AgentEngineer()
    eng.run_cli(sys.argv[1] if len(sys.argv) > 1 else "status")
'''

with open(f'{ENG}/agent_engineer.py', 'w') as f:
    f.write(agent_eng)
print("agent_engineer.py written")

# ── PROFILE ENGINEER ───────────────────────────────────────────────────
profile_eng = '''import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from engineers.base_engineer import BaseEngineer, log_action, ROOT

REQUIRED_KEYS = ["founder", "businesses", "current_focus", "cognitive_patterns", "greg_notes"]
REQUIRED_BUSINESSES = ["ZyphonOS", "GregASI", "Pikkaio"]

class ProfileEngineer(BaseEngineer):
    name = "profile_engineer"
    owned_files = ["data/ebuka_profile.json"]

    def status(self):
        profile_path = ROOT / "data" / "ebuka_profile.json"
        issues = []
        ok = []

        if not profile_path.exists():
            return {"engineer": self.name, "healthy": False,
                    "issues": ["MISSING: ebuka_profile.json not found"]}

        try:
            profile = json.load(open(profile_path, encoding="utf-8"))
        except Exception as e:
            return {"engineer": self.name, "healthy": False, "issues": [str(e)]}

        for key in REQUIRED_KEYS:
            if key in profile:
                ok.append(f"key present: {key}")
            else:
                issues.append(f"MISSING KEY: {key}")

        for biz in REQUIRED_BUSINESSES:
            if biz in profile.get("businesses", {}):
                ok.append(f"business present: {biz}")
            else:
                issues.append(f"MISSING BUSINESS: {biz}")

        log_action(self.name, "status", "data/ebuka_profile.json",
                   "issues" if issues else "healthy", str(issues))

        return {
            "engineer": self.name,
            "file": "data/ebuka_profile.json",
            "healthy": len(issues) == 0,
            "ok": ok,
            "issues": issues
        }

    def fix(self):
        status = self.status()
        if status["healthy"]:
            return {"result": "already healthy"}
        return {"result": "manual update required", "issues": status["issues"],
                "note": "Profile updates require founder instruction per blueprint section_9"}

    def update(self, data):
        profile_path = ROOT / "data" / "ebuka_profile.json"
        profile = json.load(open(profile_path, encoding="utf-8"))
        for key, val in data.items():
            if isinstance(val, dict) and isinstance(profile.get(key), dict):
                profile[key].update(val)
            else:
                profile[key] = val
        json.dump(profile, open(profile_path, "w", encoding="utf-8"), indent=2)
        log_action(self.name, "update", "data/ebuka_profile.json", "updated", str(list(data.keys())))
        return {"result": "updated", "keys": list(data.keys())}

    def expand(self, spec):
        return {"result": "use update() for profile changes"}

if __name__ == "__main__":
    eng = ProfileEngineer()
    eng.run_cli(sys.argv[1] if len(sys.argv) > 1 else "status")
'''

with open(f'{ENG}/profile_engineer.py', 'w') as f:
    f.write(profile_eng)
print("profile_engineer.py written")

# ── COORDINATOR ────────────────────────────────────────────────────────
coordinator = '''import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from engineers.api_engineer import ApiEngineer
from engineers.tick_engineer import TickEngineer
from engineers.agent_engineer import AgentEngineer
from engineers.profile_engineer import ProfileEngineer

class GregCoordinator:
    def __init__(self):
        self.engineers = {
            "api": ApiEngineer(),
            "tick": TickEngineer(),
            "agent": AgentEngineer(),
            "profile": ProfileEngineer(),
        }

    def full_status(self):
        results = {}
        all_healthy = True
        for name, eng in self.engineers.items():
            r = eng.status()
            results[name] = r
            if not r.get("healthy"):
                all_healthy = False
        return {
            "all_healthy": all_healthy,
            "engineers": results
        }

    def full_fix(self):
        results = {}
        for name, eng in self.engineers.items():
            results[name] = eng.fix()
        return results

if __name__ == "__main__":
    coord = GregCoordinator()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "status":
        r = coord.full_status()
        healthy = r["all_healthy"]
        print(f"All healthy: {healthy}")
        for name, result in r["engineers"].items():
            icon = "✓" if result.get("healthy") else "✗"
            print(f"  {icon} {name}: {len(result.get(\'issues\', []))} issues")
        if not healthy:
            print("\\nIssues:")
            for name, result in r["engineers"].items():
                for issue in result.get("issues", []):
                    print(f"  [{name}] {issue}")
    elif cmd == "fix":
        r = coord.full_fix()
        print(json.dumps(r, indent=2))
'''

with open(f'{ENG}/coordinator.py', 'w') as f:
    f.write(coordinator)
print("coordinator.py written")

print("\\nAll engineers written. Run: python3 engineers/coordinator.py status")