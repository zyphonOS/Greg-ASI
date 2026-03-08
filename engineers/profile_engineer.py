import sys, json
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
