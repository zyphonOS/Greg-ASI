import sys, json
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
            print(f"  {icon} {name}: {len(result.get('issues', []))} issues")
        if not healthy:
            print("\nIssues:")
            for name, result in r["engineers"].items():
                for issue in result.get("issues", []):
                    print(f"  [{name}] {issue}")
    elif cmd == "fix":
        r = coord.full_fix()
        print(json.dumps(r, indent=2))
