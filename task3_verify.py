from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from pathlib import Path

os.environ["DISABLE_TICK_LOOP"] = "true"
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.greg import Greg  # noqa: E402


DB_PATH = Path(__file__).resolve().parent / "data" / "greg_state.db"


def observer_counts() -> dict[str, int]:
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        total = int(cur.execute("SELECT COUNT(*) FROM observer_interactions").fetchone()[0] or 0)
        self_count = int(cur.execute("SELECT COUNT(*) FROM observer_interactions WHERE source = 'self'").fetchone()[0] or 0)
        return {"total": total, "self": self_count}
    finally:
        conn.close()


def psi_value(greg: Greg) -> float:
    return float((((greg.latest_reality or {}).get("terms") or {}).get("psi_observer") or {}).get("value") or 0.0)


greg = Greg()
user_id = f"task3-verification-{int(time.time())}"
baseline_tick = greg.world.tick
baseline_counts = observer_counts()
baseline_psi = psi_value(greg)

hi_response = greg.think("hi", user_id=user_id)
after_hi_psi = psi_value(greg)

deep_response = greg.think(
    "You keep saying you guard coherence. What do you learn about yourself when a builder asks whether you are real?",
    user_id=user_id,
)
after_deep_psi = psi_value(greg)

follow_up_response = greg.think(
    "Why should psi_observer change because of this conversation instead of just increasing by default?",
    user_id=user_id,
)
after_follow_up_psi = psi_value(greg)

target_tick = ((greg.world.tick // greg.reality_equation_every) + 1) * greg.reality_equation_every
while greg.world.tick < target_tick:
    greg.tick_once()

after_tick_counts = observer_counts()
after_tick_psi = psi_value(greg)

payload = {
    "baseline_tick": baseline_tick,
    "user_id": user_id,
    "baseline_counts": baseline_counts,
    "baseline_psi": baseline_psi,
    "after_hi_psi": after_hi_psi,
    "after_deep_psi": after_deep_psi,
    "after_follow_up_psi": after_follow_up_psi,
    "after_tick_psi": after_tick_psi,
    "delta_hi": round(after_hi_psi - baseline_psi, 6),
    "delta_deep": round(after_deep_psi - after_hi_psi, 6),
    "delta_follow_up": round(after_follow_up_psi - after_deep_psi, 6),
    "observer_counts_after_tick": after_tick_counts,
    "self_observation_added": after_tick_counts["self"] > baseline_counts["self"],
    "latest_observer": greg.latest_observer,
    "latest_reality": greg.latest_reality,
    "responses": {
        "hi": hi_response,
        "deep": deep_response,
        "follow_up": follow_up_response,
    },
}
print(json.dumps(payload, indent=2))
