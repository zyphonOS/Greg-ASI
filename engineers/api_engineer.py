import sys, json, ast
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
