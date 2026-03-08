import ast, json, os, sys
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
        f.write(json.dumps(entry) + "\n")

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
