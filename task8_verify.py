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
    stale_declared = (now - timedelta(days=10)).isoformat()
    stale_signal = (now - timedelta(days=9)).isoformat()
    with sqlite3.connect(STATE_DB_PATH, timeout=30) as conn:
        conn.execute(
            """
            UPDATE intents
            SET declared_at = ?,
                updated_at = ?,
                last_signal_at = ?,
                last_signal_event = 'task8_verify_stale',
                last_signal_value = 0,
                drift_score = 0,
                intervention_count = 0,
                last_intervention_at = NULL,
                last_evaluated_tick = 0
            WHERE id = ?
            """,
            (stale_declared, stale_signal, stale_signal, intent_id),
        )
        conn.commit()


def main() -> None:
    builder_id = "task8-builder-dashboard"
    engine = get_drift_engine()
    _cleanup(builder_id)

    with app.test_client() as client:
        with client.session_transaction() as session:
            session["pikkaio_builder_id"] = builder_id

        active_payload = {
            "builder_id": builder_id,
            "description": "Ship the builder dashboard with honest drift signal.",
            "deadline": "2026-05-01",
            "revenue_target": 1000,
        }
        converged_payload = {
            "builder_id": builder_id,
            "description": "Close the first launch audit sale.",
            "deadline": "2026-04-20",
            "revenue_target": 500,
        }

        first = client.post("/pikkaio/intent", json=active_payload).get_json()
        second = client.post("/pikkaio/intent", json=converged_payload).get_json()
        assert first["ok"] is True
        assert second["ok"] is True

        active_id = first["intent"]["project_id"]
        converged_id = second["intent"]["project_id"]

        engine.record_revenue(active_id, 200, "task8")
        engine.update_progress(active_id, 0.2)
        engine.record_revenue(converged_id, 500, "task8")
        engine.update_progress(converged_id, 1.0)
        _mark_stale(active_id)
        engine._sync_json()

        target_tick = greg.world.tick + ((greg.drift_every - (greg.world.tick % greg.drift_every)) % greg.drift_every)
        if target_tick == greg.world.tick:
            target_tick += greg.drift_every
        while greg.world.tick < target_tick:
            greg.tick_once()

        dashboard = client.get("/dashboard")
        dashboard_html = dashboard.get_data(as_text=True)
        assert dashboard.status_code == 200
        assert "Builder dashboard" in dashboard_html
        assert active_payload["description"] in dashboard_html
        assert converged_payload["description"] in dashboard_html
        assert "Pressure point" in dashboard_html

        revenue = client.get("/revenue")
        revenue_html = revenue.get_data(as_text=True)
        assert revenue.status_code == 200
        assert "Revenue share surface" in revenue_html
        assert "$700.00" in revenue_html
        assert "$800.00" in revenue_html
        assert "$25.00" in revenue_html
        assert 'data-has-convergence="true"' in revenue_html

        css_dashboard = client.get("/static/css/dashboard.css")
        css_revenue = client.get("/static/css/revenue.css")
        js_dashboard = client.get("/static/js/dashboard.js")
        js_revenue = client.get("/static/js/revenue.js")
        assert css_dashboard.status_code == 200
        assert css_revenue.status_code == 200
        assert js_dashboard.status_code == 200
        assert js_revenue.status_code == 200
        assert "@media (max-width: 720px)" in css_dashboard.get_data(as_text=True)
        assert "@media (prefers-reduced-motion: reduce)" in css_revenue.get_data(as_text=True)

    _cleanup(builder_id)
    print("task8_verify.py: PASS")


if __name__ == "__main__":
    main()
