"""
greg_pr_engine.py — The Autonomy Bridge
=========================================
Greg reads his own state.
Greg reads his own blueprint.
Greg computes the gap.
Greg generates the exact patch.
Greg opens a PR.
Ebuka approves on his phone.
Greg merges. Greg ticks forward changed.

Ebuka never writes code again.
He only says yes or no.

This is the last piece of infrastructure.
After this, Greg maintains himself.
"""

import json, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent

# ── GREG'S INTEGRATION BLUEPRINT ─────────────────────────────────────────────
# The canonical list of what should be wired into greg_living.py.
# Greg checks himself against this every time the PR engine runs.

INTEGRATION_BLUEPRINT = [
    {
        "id":       "EXP_020",
        "name":     "Predictive Coding",
        "module":   "greg_predictive",
        "function": "run_predictive_cycle",
        "file":     "greg_predictive.py",
        "detect":   "from greg_predictive import",
        "wire_after": "# EXP_019",
        "code": '''
        # EXP_020 — Predictive Coding
        try:
            from greg_predictive import load_predictive_model, save_predictive_model
            _pred_model = load_predictive_model()
            _pre_state = {
                "tick": tick_num - 1,
                "civilization_health_pct": int(self.state.get("phase3_convergence", 0.66) * 100),
                "dominant_drive": max(self.state.drives(), key=self.state.drives().get),
                "agent_count": len((self.state.get("civilization") or {}).get("agents", {})),
                "memory_count": len(self.state.get("memory", [])),
                "drives": self.state.drives(),
                "health_momentum": 0.0,
            }
            _post_state = {
                "tick": tick_num,
                "civilization_health_pct": int(self.state.get("phase3_convergence", 0.66) * 100),
                "dominant_drive": max(self.state.drives(), key=self.state.drives().get),
                "agent_count": len((self.state.get("civilization") or {}).get("agents", {})),
                "memory_count": len(self.state.get("memory", [])),
            }
            _pred, _surprise, _narration = __import__("greg_predictive").run_predictive_cycle(_pre_state, _post_state, _pred_model)
            self.state.set("predictive_surprise", _surprise)
            self.state.set("predictive_voice", _narration)
            save_predictive_model(_pred_model)
        except Exception: pass
''',
    },
    {
        "id":       "EXP_021",
        "name":     "Hebbian Knowledge",
        "module":   "greg_hebbian",
        "function": "hebbian_tick",
        "file":     "greg_hebbian.py",
        "detect":   "from greg_hebbian import",
        "wire_after": "# EXP_020",
        "code": '''
        # EXP_021 — Hebbian Knowledge
        try:
            from greg_hebbian import HebbianGraph, hebbian_tick as _hebb_tick, HEBBIAN_PATH
            if not hasattr(self, "_hebbian_graph"):
                self._hebbian_graph = HebbianGraph.load(HEBBIAN_PATH)
            _hebb_tick(
                self._hebbian_graph,
                result.get("action", "reflect"),
                self.state.get("location", "spawn"),
                self.state.drives(),
                tick_num,
            )
            if tick_num % 50 == 0:
                self._hebbian_graph.save(HEBBIAN_PATH)
                self.state.set("hebbian_summary", self._hebbian_graph.summary())
        except Exception: pass
''',
    },
    {
        "id":       "EXP_022",
        "name":     "Emotional Memory Consolidation",
        "module":   "greg_emotional_consolidation",
        "function": "EmotionalConsolidationEngine",
        "file":     "greg_emotional_consolidation.py",
        "detect":   "from greg_emotional_consolidation import",
        "wire_after": "# EXP_021",
        "code": '''
        # EXP_022 — Emotional Memory Consolidation
        try:
            from greg_emotional_consolidation import EmotionalConsolidationEngine, CONSOLIDATION_PATH
            if not hasattr(self, "_consolidation_engine"):
                self._consolidation_engine = EmotionalConsolidationEngine.load(CONSOLIDATION_PATH)
            _surprise_score = (self.state.get("predictive_surprise") or {}).get("surprise_score", 0.0)
            _cons_result = self._consolidation_engine.consider(
                tick_num,
                {"action": result.get("action","reflect"),
                 "location": self.state.get("location","spawn"),
                 "alerts": result.get("alerts", [])},
                self.state.drives(),
                _surprise_score,
            )
            if _cons_result.get("consolidates"):
                self.state.log_memory("emotional_consolidation",
                    _cons_result.get("memory_formed", {}).get("description", ""),
                    emotional_weight=_cons_result.get("score", 0.5))
            if tick_num % 50 == 0:
                self._consolidation_engine.save(CONSOLIDATION_PATH)
                self.state.set("consolidation_summary", self._consolidation_engine.summary())
        except Exception: pass
''',
    },
    {
        "id":       "EXP_023",
        "name":     "Reality Sensors",
        "module":   "greg_sensors",
        "function": "read_reality",
        "file":     "greg_sensors.py",
        "detect":   "from greg_sensors import",
        "wire_after": "# EXP_022",
        "code": '''
        # EXP_023 — Reality Sensors
        try:
            from greg_sensors import read_reality
            _reality = read_reality(tick_num)
            self.state.set("reality", _reality)
            self.state.set("greg_speaks_reality", _reality.get("greg_speaks", ""))
        except Exception: pass
''',
    },
    {
        "id":       "EXP_024",
        "name":     "Sparse Activation",
        "module":   "greg_sparse",
        "function": "SparseActivationEngine",
        "file":     "greg_sparse.py",
        "detect":   "from greg_sparse import",
        "wire_after": "# EXP_023",
        "code": '''
        # EXP_024 — Sparse Activation
        try:
            from greg_sparse import SparseActivationEngine, SPARSE_PATH
            if not hasattr(self, "_sparse_engine"):
                self._sparse_engine = SparseActivationEngine.load(SPARSE_PATH)
            _civ = self.state.get("civilization") or {}
            _agents = _civ.get("agents", {})
            if _agents:
                _sparse_result = self._sparse_engine.activate(
                    _agents,
                    {"drives": self.state.drives(), "location": self.state.get("location","spawn")},
                    tick_num,
                )
                self.state.set("sparse_activation", _sparse_result)
                if tick_num % 100 == 0:
                    self._sparse_engine.save(SPARSE_PATH)
        except Exception: pass
''',
    },
    {
        "id":       "SCHOOL",
        "name":     "Greg School — Experiential Language",
        "module":   "greg_school",
        "function": "school_tick",
        "file":     "greg_school.py",
        "detect":   "from greg_school import",
        "wire_after": "# EXP_024",
        "code": '''
        # SCHOOL — Experiential Language Acquisition
        try:
            from greg_school import school_tick as _school_tick
            _surprise_level = (self.state.get("predictive_surprise") or {}).get("surprise_level", "NONE")
            _memory_formed  = bool((self.state.get("consolidation_summary") or {}).get("total", 0) >
                                   getattr(self, "_prev_memory_count", 0))
            setattr(self, "_prev_memory_count",
                    (self.state.get("consolidation_summary") or {}).get("total", 0))
            _school_result = _school_tick(
                tick_num,
                result.get("action","reflect"),
                self.state.get("location","spawn"),
                self.state.drives(),
                _surprise_level,
                result.get("alerts",[]),
                _memory_formed,
            )
            self.state.set("school_label", _school_result.get("label",""))
        except Exception: pass
''',
    },
]


# ── SELF-CHECKER ──────────────────────────────────────────────────────────────

class GregSelfChecker:
    """
    Greg reads greg_living.py and checks what's wired.
    Returns a list of missing integrations.
    """

    def __init__(self, living_path: str = None):
        self.living_path = living_path or str(ROOT / "greg_living.py")

    def read_living(self) -> str:
        try:
            return open(self.living_path, encoding="utf-8").read()
        except:
            return ""

    def check(self) -> dict:
        """Check which integrations are present vs missing."""
        code = self.read_living()
        results = {}
        for integration in INTEGRATION_BLUEPRINT:
            present = integration["detect"] in code
            results[integration["id"]] = {
                "name":    integration["name"],
                "present": present,
                "file_exists": os.path.exists(ROOT / integration["file"]),
            }
        missing = [k for k, v in results.items()
                   if not v["present"] and v["file_exists"]]
        return {
            "integrations": results,
            "missing":      missing,
            "all_wired":    len(missing) == 0,
        }


# ── DIFF GENERATOR ────────────────────────────────────────────────────────────

class DiffGenerator:
    """
    Generates the exact patch needed to wire missing integrations.
    Finds the right insertion point in greg_living.py.
    """

    def __init__(self, living_path: str = None):
        self.living_path = living_path or str(ROOT / "greg_living.py")

    def generate_patch(self, missing_ids: list) -> dict:
        """Generate the code patch for missing integrations."""
        code = open(self.living_path, encoding="utf-8").read()

        # Find the insertion point — after Phase 3 block, before save
        # Look for the save call at end of tick()
        insertion_marker = "        # Save state\n        self.state.save()"
        if insertion_marker not in code:
            # Fallback — try to find save()
            insertion_marker = "        self.state.save()"

        if insertion_marker not in code:
            return {"ok": False, "error": "Cannot find insertion point in greg_living.py"}

        # Build the code to insert
        lines_to_add = []
        for exp_id in missing_ids:
            blueprint = next((b for b in INTEGRATION_BLUEPRINT if b["id"] == exp_id), None)
            if blueprint:
                lines_to_add.append(blueprint["code"])

        if not lines_to_add:
            return {"ok": False, "error": "No valid integrations to add"}

        insert_block = "\n".join(lines_to_add)

        new_code = code.replace(
            insertion_marker,
            insert_block + "\n        " + insertion_marker.strip()
        )

        return {
            "ok":           True,
            "original_len": len(code),
            "new_len":      len(new_code),
            "added_ids":    missing_ids,
            "new_code":     new_code,
        }


# ── PR ENGINE ─────────────────────────────────────────────────────────────────

class GregPREngine:
    """
    Greg's autonomy bridge.
    
    Reads his own state → finds gaps → generates patch →
    writes branch → opens PR → waits for Ebuka to approve.
    
    Ebuka never writes code again.
    He only says yes or no.
    """

    def __init__(self):
        self.checker   = GregSelfChecker()
        self.generator = DiffGenerator()

    def run(self, dry_run: bool = False) -> dict:
        """
        Full PR cycle.
        dry_run=True: generate patch but don't create PR.
        """
        print("[PR Engine] Greg is checking himself...")

        # 1. Check what's missing
        check = self.checker.check()
        missing = check["missing"]

        if not missing:
            print("[PR Engine] All integrations present. Nothing to wire.")
            return {"status": "nothing_to_do", "check": check}

        print(f"[PR Engine] Missing integrations: {missing}")

        # 2. Generate patch
        patch = self.generator.generate_patch(missing)
        if not patch["ok"]:
            print(f"[PR Engine] Patch generation failed: {patch.get('error')}")
            return {"status": "patch_failed", "error": patch.get("error")}

        print(f"[PR Engine] Patch ready. Adding {len(missing)} integrations.")

        if dry_run:
            return {
                "status":    "dry_run",
                "missing":   missing,
                "patch_len": patch["new_len"],
                "preview":   patch["new_code"][:500] + "...",
            }

        # 3. Write the patched file
        try:
            with open(self.checker.living_path, "w", encoding="utf-8") as f:
                f.write(patch["new_code"])
            print(f"[PR Engine] greg_living.py patched successfully.")
        except Exception as e:
            return {"status": "write_failed", "error": str(e)}

        # 4. Git operations — create branch, commit, push, open PR
        branch = f"greg-auto-wire-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        pr_result = self._git_pr(branch, missing, patch)

        return {
            "status":    "pr_created" if pr_result["ok"] else "git_failed",
            "missing":   missing,
            "branch":    branch,
            "pr":        pr_result,
        }

    def _git_pr(self, branch: str, missing: list, patch: dict) -> dict:
        """Create git branch, commit, push, open PR."""
        try:
            # Configure git
            self._run(["git", "config", "user.name",  "Greg ASI"])
            self._run(["git", "config", "user.email", "greg@zyphonos.io"])

            # Create branch
            self._run(["git", "checkout", "-b", branch])

            # Stage the changed file
            self._run(["git", "add", "greg_living.py"])

            # Also stage any new module files
            for exp_id in missing:
                blueprint = next((b for b in INTEGRATION_BLUEPRINT if b["id"] == exp_id), None)
                if blueprint:
                    fname = blueprint["file"]
                    if os.path.exists(fname):
                        self._run(["git", "add", fname])

            # Commit
            names = [next(b["name"] for b in INTEGRATION_BLUEPRINT if b["id"] == i)
                     for i in missing]
            msg = f"[greg-auto] Wire {', '.join(missing)}: {', '.join(names)}"
            self._run(["git", "commit", "-m", msg])

            # Push
            self._run(["git", "push", "origin", branch])

            # Return PR info — GitHub CLI would open PR here
            # For now: return the branch info so PR can be opened manually
            # or via GitHub Actions
            return {
                "ok":     True,
                "branch": branch,
                "commit": msg,
                "pr_title": f"Greg self-wires: {', '.join(missing)}",
                "pr_body":  self._pr_body(missing, names),
                "note": "Push succeeded. Open PR at: "
                        f"https://github.com/{os.environ.get('GITHUB_REPOSITORY','zyphonOS/Greg-ASI')}"
                        f"/compare/{branch}",
            }

        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _run(self, cmd: list) -> str:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
        if result.returncode != 0:
            raise Exception(f"{' '.join(cmd)}: {result.stderr}")
        return result.stdout.strip()

    def _pr_body(self, missing: list, names: list) -> str:
        lines = [
            "## Greg self-wired the following integrations",
            "",
            "Greg read his own state, found gaps, and generated this patch.",
            "No human wrote this code.",
            "",
            "### Integrations added:",
        ]
        for exp_id, name in zip(missing, names):
            lines.append(f"- **{exp_id}**: {name}")
        lines += [
            "",
            "### What to check:",
            "- [ ] `greg_living.py` tick loop compiles",
            "- [ ] GitHub Actions run succeeds after merge",
            "- [ ] Greg's state JSON updates correctly",
            "",
            "### To approve:",
            "Merge this PR. Greg will pick up the changes on next tick.",
            "",
            "— Greg",
        ]
        return "\n".join(lines)


# ── STATUS REPORT ─────────────────────────────────────────────────────────────

def greg_status_report() -> str:
    """Greg reports his own integration status."""
    checker = GregSelfChecker()
    check   = checker.check()

    lines = ["Greg's self-assessment:"]
    for exp_id, info in check["integrations"].items():
        icon = "✓" if info["present"] else ("⚠" if info["file_exists"] else "✗")
        lines.append(f"  {icon} {exp_id} — {info['name']}")
        if not info["present"] and info["file_exists"]:
            lines.append(f"      → Module exists but not wired. PR engine will fix this.")
        elif not info["file_exists"]:
            lines.append(f"      → Module file not found.")

    if check["all_wired"]:
        lines.append("\nAll integrations present. I am complete.")
    else:
        lines.append(f"\n{len(check['missing'])} integrations missing.")
        lines.append("Running PR engine will wire them autonomously.")

    return "\n".join(lines)


if __name__ == "__main__":
    print("=" * 60)
    print("greg_pr_engine.py — The Autonomy Bridge")
    print("=" * 60)

    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "status":
        print(greg_status_report())

    elif cmd == "dry-run":
        engine = GregPREngine()
        result = engine.run(dry_run=True)
        print(f"\nStatus: {result['status']}")
        if result.get("missing"):
            print(f"Would wire: {result['missing']}")
        if result.get("preview"):
            print(f"Preview:\n{result['preview']}")

    elif cmd == "run":
        engine = GregPREngine()
        result = engine.run(dry_run=False)
        print(json.dumps(result, indent=2))

    else:
        print(f"Usage: python3 greg_pr_engine.py [status|dry-run|run]")
