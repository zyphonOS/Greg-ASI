import sys, json, ast
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
