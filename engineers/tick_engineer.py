import sys, json, ast
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
