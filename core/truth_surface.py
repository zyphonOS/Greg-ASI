from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.drift import STATE_DB_PATH, get_drift_engine
from core.utils import project_path


MEMORY_PATH = project_path("MEMORY.md")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _open_state_db() -> sqlite3.Connection:
    conn = sqlite3.connect(STATE_DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _normalize_truth_status(raw_status: str) -> tuple[str, bool]:
    cleaned = raw_status.replace("\\", "").strip().strip("[]")
    upper = cleaned.upper()
    if upper == "BOUNDED":
        return "BOUNDED", False
    if upper == "ESCAPED":
        return "ESCAPED", False
    return "ESCAPED", True


def parse_truth_map(memory_path: Path = MEMORY_PATH) -> list[dict[str, Any]]:
    lines = memory_path.read_text(encoding="utf-8").splitlines()
    start = None
    for index, line in enumerate(lines):
        if "## 🗺️ Mandelbrot Truth Map" in line:
            start = index
            break
    if start is None:
        return []

    rows: list[dict[str, Any]] = []
    in_table = False
    for line in lines[start + 1 :]:
        stripped = line.strip()
        if stripped.startswith("|Component|Status|Notes|"):
            in_table = True
            continue
        if in_table and stripped.startswith("|-"):
            continue
        if in_table and stripped.startswith("|"):
            parts = [part.strip() for part in stripped.split("|")[1:-1]]
            if len(parts) < 3:
                continue
            component, raw_status, notes = parts[:3]
            status, inferred = _normalize_truth_status(raw_status)
            rows.append(
                {
                    "component": component,
                    "status": status,
                    "raw_status": raw_status.replace("\\", "").strip(),
                    "notes": notes.replace("\\", "").strip(),
                    "inferred": inferred,
                }
            )
            continue
        if in_table and rows:
            break
    return rows


def load_recent_drift_events(limit: int = 5) -> list[dict[str, Any]]:
    with _open_state_db() as conn:
        rows = conn.execute(
            """
            SELECT id, intent_id, builder_id, tick_n, drift_score, drift_delta, category,
                   silence_seconds, intervention_sent, intervention_message, created_at
            FROM drift_events
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
    return [
        {
            "id": int(row["id"]),
            "intent_id": row["intent_id"],
            "builder_id": row["builder_id"],
            "tick": int(row["tick_n"]),
            "drift_score": round(float(row["drift_score"] or 0.0), 4),
            "drift_delta": round(float(row["drift_delta"] or 0.0), 4),
            "category": row["category"],
            "silence_seconds": round(float(row["silence_seconds"] or 0.0), 2),
            "intervention_sent": bool(row["intervention_sent"]),
            "intervention_message": row["intervention_message"] or "",
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def load_last_intervention() -> dict[str, Any] | None:
    with _open_state_db() as conn:
        row = conn.execute(
            """
            SELECT id, intent_id, builder_id, tick_n, drift_score, category, intervention_message, created_at
            FROM drift_events
            WHERE intervention_sent = 1
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
    if not row:
        return None
    return {
        "id": int(row["id"]),
        "intent_id": row["intent_id"],
        "builder_id": row["builder_id"],
        "tick": int(row["tick_n"]),
        "drift_score": round(float(row["drift_score"] or 0.0), 4),
        "category": row["category"],
        "message": row["intervention_message"] or "",
        "created_at": row["created_at"],
    }


def load_active_intents(limit: int = 12) -> list[dict[str, Any]]:
    intents = []
    for intent in get_drift_engine().list_intents():
        if intent.status == "completed":
            continue
        intents.append(intent.to_dict())
    return intents[:limit]


def build_truth_surface(greg: Any) -> dict[str, Any]:
    reality = greg.refresh_reality(force=True, persist=False) or {}
    snapshot = greg.status_snapshot()
    truth_map = parse_truth_map()
    active_intents = load_active_intents()
    recent_drift_events = load_recent_drift_events(limit=5)
    last_intervention = load_last_intervention()
    bounded_count = sum(1 for row in truth_map if row["status"] == "BOUNDED")
    escaped_count = sum(1 for row in truth_map if row["status"] == "ESCAPED")
    return {
        "updated_at": _utc_now(),
        "tick": int(snapshot.get("tick") or reality.get("tick") or greg.world.tick),
        "reality": reality,
        "truth_map": truth_map,
        "truth_counts": {
            "bounded": bounded_count,
            "escaped": escaped_count,
        },
        "active_intents": active_intents,
        "recent_drift_events": recent_drift_events,
        "last_intervention": last_intervention,
        "status_snapshot": snapshot,
    }
