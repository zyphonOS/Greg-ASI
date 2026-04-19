"""Task 7 verification — Command Locus + Live Truth Surface."""
import sys
import os
import py_compile
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS = []
FAIL = []

def check(label, fn):
    try:
        fn()
        PASS.append(label)
    except Exception as e:
        FAIL.append((label, str(e)))

# 1. Compile checks
check("command_locus compiles",
    lambda: py_compile.compile("core/command_locus.py", doraise=True))
check("truth_surface compiles",
    lambda: py_compile.compile("core/truth_surface.py", doraise=True))
check("main.py compiles",
    lambda: py_compile.compile("main.py", doraise=True))

# 2. truth.html exists
check("truth.html exists",
    lambda: open("templates/truth.html").close())

# 3. CommandLocus instantiates and dispatches unknown action cleanly
def _locus_dispatch():
    from unittest.mock import MagicMock
    from core.command_locus import CommandLocus
    greg = MagicMock()
    greg.world.tick = 1
    locus = CommandLocus(greg=greg, agent_manager=MagicMock())
    body, code = locus.dispatch("unknown_xyz", {})
    assert code == 400
    assert body["ok"] is False
check("CommandLocus dispatch rejects unknown action", _locus_dispatch)

# 4. CommandLocus think action routes correctly
def _locus_think():
    from unittest.mock import MagicMock
    from core.command_locus import CommandLocus
    greg = MagicMock()
    greg.world.tick = 42
    greg.think.return_value = "test response"
    locus = CommandLocus(greg=greg, agent_manager=MagicMock())
    body, code = locus.dispatch("think", {"prompt": "hello", "mode": "presence", "user_id": "test"})
    assert code == 200
    assert body["ok"] is True
    assert body["tick"] == 42
check("CommandLocus think action routes to greg.think", _locus_think)

# 5. alias resolution
def _alias():
    from unittest.mock import MagicMock
    from core.command_locus import CommandLocus
    locus = CommandLocus(greg=MagicMock(), agent_manager=MagicMock())
    assert locus._normalize_action("ask") == "think"
    assert locus._normalize_action("say") == "think"
    assert locus._normalize_action("hello") == "speak_first"
check("CommandLocus aliases resolve correctly", _alias)

# 6. truth_surface imports and key structure
def _truth_keys():
    from unittest.mock import MagicMock, patch
    from core.truth_surface import build_truth_surface
    greg = MagicMock()
    greg.world.tick = 10
    greg.refresh_reality.return_value = {"R": 0.5, "tick": 10, "terms": {}, "weakest_term": None}
    greg.status_snapshot.return_value = {"tick": 10}
    with patch("core.truth_surface.parse_truth_map", return_value=[]):
        with patch("core.truth_surface.load_active_intents", return_value=[]):
            with patch("core.truth_surface.load_recent_drift_events", return_value=[]):
                with patch("core.truth_surface.load_last_intervention", return_value=None):
                    result = build_truth_surface(greg)
    required = ["tick","reality","truth_map","truth_counts","active_intents","recent_drift_events","last_intervention"]
    for key in required:
        assert key in result, f"Missing key: {key}"
check("build_truth_surface returns all required keys", _truth_keys)

# 7. /truth route registered in app
def _truth_route():
    import os; os.environ.setdefault("DISABLE_TICK_LOOP","true")
    from main import app
    rules = [r.rule for r in app.url_map.iter_rules()]
    assert "/truth" in rules, f"/truth not found in routes: {rules}"
check("/truth route registered in Flask app", _truth_route)

# 8. /api/greg/command route registered
def _command_route():
    import os; os.environ.setdefault("DISABLE_TICK_LOOP","true")
    from main import app
    rules = [r.rule for r in app.url_map.iter_rules()]
    assert "/api/greg/command" in rules
check("/api/greg/command route registered", _command_route)

# Report
print("\n--- Task 7 Verification ---")
for label in PASS:
    print(f"  PASS  {label}")
for label, err in FAIL:
    print(f"  FAIL  {label}")
    print(f"        {err}")

if FAIL:
    print(f"\ntask7_verify.py: FAIL ({len(FAIL)} failures)")
    sys.exit(1)
else:
    print(f"\ntask7_verify.py: PASS ({len(PASS)} checks)")