from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone


os.environ["DISABLE_TICK_LOOP"] = "true"

from core.drift import STATE_DB_PATH, get_drift_engine  # noqa: E402
from main import app, greg  # noqa: E402


def _cleanup(builder_id: str) -> None:
    with sqlite3.connect(STATE_DB_PATH, timeout=30) as conn:
        conn.execute("DELETE FROM drift_events WHERE builder_id = ?", (builder_id,))
        conn.execute("DELETE FROM intents WHERE builder_id = ?", (builder_id,))
        conn.commit()
    get_drift_engine()._sync_json()


def _mark_stale(intent_id: str) -> None:
    now = datetime.now(timezone.utc)
    stale_declared = (now - timedelta(days=11)).isoformat()
    stale_signal = (now - timedelta(days=9)).isoformat()
    with sqlite3.connect(STATE_DB_PATH, timeout=30) as conn:
        conn.execute(
            """
            UPDATE intents
            SET progress = 0,
                status = 'active',
                declared_at = ?,
                updated_at = ?,
                last_signal_at = ?,
                last_signal_event = 'task5_verify_stale',
                last_signal_value = 0,
                drift_score = 0,
                intervention_count = 0,
                last_intervention_at = NULL,
                last_evaluated_tick = 0,
                metadata_json = '{"signal_log": [], "interventions": [], "maze_layer": "declaration"}'
            WHERE id = ?
            """,
            (stale_declared, stale_signal, stale_signal, intent_id),
        )
        conn.commit()


def main() -> None:
    builder_id = "task5-builder-surface"
    _cleanup(builder_id)

    with app.test_client() as client:
        with client.session_transaction() as session:
            session["pikkaio_builder_id"] = builder_id

        board = client.get("/pikkaio", follow_redirects=True)
        board_text = board.get_data(as_text=True)
        assert board.status_code == 200
        assert "Declare the line you are actually building." in board_text
        assert "pikkaio_logo.png" in board_text
        assert "Current trajectory" in board_text

        css = client.get("/static/css/pikkaio.css")
        css_text = css.get_data(as_text=True)
        assert css.status_code == 200
        assert "@media (max-width: 720px)" in css_text

        payload = {
            "description": "Launch a builder-facing intent surface that exposes drift clearly.",
            "deadline": "2026-04-30",
            "revenue_target": 3500,
            "builder_id": builder_id,
        }
        declared = client.post("/pikkaio/intent", json=payload)
        assert declared.status_code == 200, declared.get_data(as_text=True)
        declared_json = declared.get_json()
        assert declared_json["ok"] is True
        assert declared_json["builder_id"] == builder_id
        assert "Intent received" in declared_json["acknowledgement"] or "tracked" in declared_json["acknowledgement"].lower()
        intent_id = declared_json["intent"]["project_id"]

        with sqlite3.connect(STATE_DB_PATH, timeout=30) as conn:
            row = conn.execute(
                "SELECT builder_id, description, deadline, revenue_target FROM intents WHERE id = ?",
                (intent_id,),
            ).fetchone()
        assert row is not None
        assert row[0] == builder_id
        assert row[1] == payload["description"]

        status_before = client.get("/pikkaio/status")
        before_json = status_before.get_json()
        assert before_json["ok"] is True
        assert before_json["has_intent"] is True
        assert before_json["intent"]["project_id"] == intent_id
        assert before_json["acknowledgement"]

        _mark_stale(intent_id)
        get_drift_engine()._sync_json()

        target_tick = greg.world.tick + ((greg.drift_every - (greg.world.tick % greg.drift_every)) % greg.drift_every)
        if target_tick == greg.world.tick:
            target_tick += greg.drift_every
        while greg.world.tick < target_tick:
            greg.tick_once()

        status_after = client.get("/pikkaio/status")
        after_json = status_after.get_json()
        assert after_json["ok"] is True
        assert after_json["drift_score"] is not None
        assert after_json["drift_score"] >= 0.65, after_json
        assert after_json["intervention"] is not None, after_json
        assert after_json["intervention"]["message"], after_json

        board_after = client.get("/pikkaio", follow_redirects=True)
        after_text = board_after.get_data(as_text=True)
        assert "Pikkaio acknowledgement" in after_text
        assert "Intervention" in after_text

    _cleanup(builder_id)
    print("task5_verify.py: PASS")


if __name__ == "__main__":
    main()
