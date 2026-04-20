from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from flask import Blueprint, render_template, session

from constitution_runtime import build_protection_state, constitutional_revenue_allocation
from core.utils import data_path
from layers.legacy.pikkaio.routes import _builder_id, _builder_intents


dashboard_bp = Blueprint("pikkaio_dashboard", __name__)

STATE_DB_PATH = data_path("greg_state.db")
MEMORY_DB_PATH = data_path("greg_memory.db")


def _latest_reality_snapshot() -> dict:
    try:
        conn = sqlite3.connect(MEMORY_DB_PATH, timeout=30)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT tick, reality_score, epsilon, weakest_term, generated_at
            FROM reality_equation_snapshots
            ORDER BY tick DESC
            LIMIT 1
            """
        ).fetchone()
        conn.close()
        if not row:
            return {"tick": 0, "reality_score": 0.0, "epsilon": 0.0, "weakest_term": "unknown", "generated_at": ""}
        return {
            "tick": int(row["tick"] or 0),
            "reality_score": float(row["reality_score"] or 0.0),
            "epsilon": float(row["epsilon"] or 0.0),
            "weakest_term": row["weakest_term"] or "unknown",
            "generated_at": row["generated_at"] or "",
        }
    except Exception:
        return {"tick": 0, "reality_score": 0.0, "epsilon": 0.0, "weakest_term": "unknown", "generated_at": ""}


def _latest_intervention(intent_id: str) -> dict | None:
    try:
        conn = sqlite3.connect(STATE_DB_PATH, timeout=30)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT intervention_message, created_at, tick_n, drift_score
            FROM drift_events
            WHERE intent_id = ? AND intervention_sent = 1
            ORDER BY id DESC
            LIMIT 1
            """,
            (intent_id,),
        ).fetchone()
        conn.close()
        if not row:
            return None
        return {
            "message": row["intervention_message"] or "",
            "created_at": row["created_at"] or "",
            "tick": int(row["tick_n"] or 0),
            "drift_score": round(float(row["drift_score"] or 0.0), 4),
        }
    except Exception:
        return None


def _builder_latest_intervention(builder_id: str) -> dict | None:
    try:
        conn = sqlite3.connect(STATE_DB_PATH, timeout=30)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT intent_id, intervention_message, created_at, tick_n, drift_score
            FROM drift_events
            WHERE builder_id = ? AND intervention_sent = 1
            ORDER BY id DESC
            LIMIT 1
            """,
            (builder_id,),
        ).fetchone()
        conn.close()
        if not row:
            return None
        return {
            "intent_id": row["intent_id"],
            "message": row["intervention_message"] or "",
            "created_at": row["created_at"] or "",
            "tick": int(row["tick_n"] or 0),
            "drift_score": round(float(row["drift_score"] or 0.0), 4),
        }
    except Exception:
        return None


def _days_since(iso_value: str) -> int:
    try:
        then = datetime.fromisoformat(iso_value)
        now = datetime.now(timezone.utc)
        return max(0, (now - then).days)
    except Exception:
        return 0


@dashboard_bp.route("/dashboard")
def dashboard():
    builder_id = _builder_id(create=True)
    intents = _builder_intents(builder_id)
    reality = _latest_reality_snapshot()
    confirmed_revenue = round(sum(float(intent.revenue_usd or 0.0) for intent in intents), 2)
    finance = constitutional_revenue_allocation(confirmed_revenue, treasury_balance=confirmed_revenue * 0.2)

    dashboard_intents = []
    drifting_count = 0
    max_drift = 0.0
    for intent in intents:
        intervention = _latest_intervention(intent.id)
        drifting_count += 1 if float(intent.drift_score or 0.0) >= 0.45 else 0
        max_drift = max(max_drift, float(intent.drift_score or 0.0))
        dashboard_intents.append(
            {
                "id": intent.id,
                "description": intent.description,
                "status": intent.status,
                "drift_score": round(float(intent.drift_score or 0.0), 4),
                "progress": round(float(intent.progress or 0.0), 4),
                "convergence_pct": intent.convergence_pct(),
                "deadline": intent.deadline or "",
                "last_signal_at": intent.last_signal_at,
                "days_since_activity": _days_since(intent.last_signal_at),
                "last_intervention": intervention,
                "revenue_usd": round(float(intent.revenue_usd or 0.0), 2),
            }
        )

    dashboard_intents.sort(key=lambda item: item["drift_score"], reverse=True)
    latest_intervention = _builder_latest_intervention(builder_id)

    dashboard_state = {
        "builder_id": builder_id,
        "intent_count": len(dashboard_intents),
        "drifting_count": drifting_count,
        "anchored_count": max(0, len(dashboard_intents) - drifting_count),
        "max_drift": round(max_drift, 4),
        "epsilon": round(float(reality["epsilon"]), 4),
        "reality_tick": int(reality["tick"]),
        "reality_score": round(float(reality["reality_score"]), 6),
        "weakest_term": reality["weakest_term"],
        "latest_intervention": latest_intervention,
        "confirmed_revenue": confirmed_revenue,
    }

    return render_template(
        "dashboard.html",
        dashboard=dashboard_state,
        finance=finance,
        intents=dashboard_intents,
        protection=build_protection_state(
            session,
            surface="Dashboard",
            required_roles=("founder", "builder", "community", "admin"),
        ),
    )
