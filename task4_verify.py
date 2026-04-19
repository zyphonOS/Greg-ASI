from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from pathlib import Path

os.environ["DISABLE_TICK_LOOP"] = "true"
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core.drift import STATE_DB_PATH, get_drift_engine  # noqa: E402
from core.greg import Greg  # noqa: E402


def epsilon_value(greg: Greg) -> float:
    return float((((greg.latest_reality or {}).get("terms") or {}).get("epsilon") or {}).get("value") or 0.0)


def row_counts(intent_id: str) -> dict[str, int]:
    conn = sqlite3.connect(STATE_DB_PATH)
    try:
        cur = conn.cursor()
        return {
            "intent_rows": int(cur.execute("SELECT COUNT(*) FROM intents WHERE id = ?", (intent_id,)).fetchone()[0] or 0),
            "drift_events": int(cur.execute("SELECT COUNT(*) FROM drift_events WHERE intent_id = ?", (intent_id,)).fetchone()[0] or 0),
            "intervention_events": int(
                cur.execute(
                    "SELECT COUNT(*) FROM drift_events WHERE intent_id = ? AND intervention_sent = 1",
                    (intent_id,),
                ).fetchone()[0]
                or 0
            ),
        }
    finally:
        conn.close()


def cleanup_task4_rows() -> None:
    conn = sqlite3.connect(STATE_DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM drift_events WHERE builder_id LIKE 'task4-%'")
        cur.execute("DELETE FROM intents WHERE builder_id LIKE 'task4-%'")
        conn.commit()
    finally:
        conn.close()


cleanup_task4_rows()
greg = Greg()
engine = get_drift_engine()
engine._sync_json()
user_id = f"task4-verification-{int(time.time())}"
intent = engine.declare_intent(
    builder_id=user_id,
    description="Ship a founder operating system, stay visible every week, and close the first customer this month.",
    deadline="2026-04-30",
    revenue_target=1000.0,
)

baseline_counts = row_counts(intent.id)
epsilon_before = epsilon_value(greg)

conn = sqlite3.connect(STATE_DB_PATH)
try:
    stale_ts = "2026-03-01T00:00:00+00:00"
    conn.execute(
        """
        UPDATE intents
        SET declared_at = ?, updated_at = ?, last_signal_at = ?, progress = ?, revenue_usd = ?, last_evaluated_tick = 0
        WHERE id = ?
        """,
        (stale_ts, stale_ts, stale_ts, 0.02, 0.0, intent.id),
    )
    conn.commit()
finally:
    conn.close()

target_tick = ((greg.world.tick // greg.drift_every) + 1) * greg.drift_every
while greg.world.tick < target_tick:
    greg.tick_once()

updated_intent = engine.get_intent(intent.id)
epsilon_after = epsilon_value(greg)
counts_after = row_counts(intent.id)
interventions = (greg.latest_pikkaio or {}).get("interventions") or []

payload = {
    "user_id": user_id,
    "intent_id": intent.id,
    "baseline_tick": target_tick - greg.drift_every,
    "current_tick": greg.world.tick,
    "epsilon_before": epsilon_before,
    "epsilon_after": epsilon_after,
    "epsilon_delta": round(epsilon_after - epsilon_before, 6),
    "rows_before": baseline_counts,
    "rows_after": counts_after,
    "intent": updated_intent.to_dict() if updated_intent else None,
    "latest_pikkaio": greg.latest_pikkaio,
    "latest_drift": greg.latest_drift,
    "intervention_triggered": counts_after["intervention_events"] > baseline_counts["intervention_events"],
    "intervention_messages": interventions,
    "verification": {
        "drift_score_recorded": bool(updated_intent and updated_intent.drift_score >= 0.65),
        "sqlite_rows_written": counts_after["drift_events"] > baseline_counts["drift_events"],
        "intervention_logged": counts_after["intervention_events"] > baseline_counts["intervention_events"],
        "tick_cadence_ran": greg.world.tick == target_tick,
        "epsilon_changed": abs(epsilon_after - epsilon_before) >= 0.005,
    },
}

cleanup_task4_rows()
engine._sync_json()

print(json.dumps(payload, indent=2))
