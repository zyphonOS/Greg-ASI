from __future__ import annotations

import json
import math
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.utils import data_path, write_json


STATE_DB_PATH = data_path("greg_state.db")
PIKKAIO_JSON_PATH = data_path("greg_pikkaio.json")
DRIFT_EVERY_TICKS = 10
DRIFT_WARN = 0.45
DRIFT_INTERVENE = 0.65
DRIFT_CRITICAL = 0.85
SILENCE_SOFT = 3 * 86400
SILENCE_HARD = 7 * 86400
SILENCE_MAX = 14 * 86400
INTERVENTION_COOLDOWN_SECONDS = 18 * 3600
MAX_SIGNAL_LOG = 50
MAX_INTERVENTIONS = 20
MAX_TOP_DRIFTERS = 5
_LOCK = threading.Lock()
_ENGINE: "DriftEngine | None" = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _norm_log(value: float, scale: float) -> float:
    if scale <= 0:
        return 0.0
    return _clamp(math.log1p(max(value, 0.0)) / math.log1p(scale))


def _parse_ts(value: str | None) -> float:
    if not value:
        return time.time()
    try:
        return datetime.fromisoformat(value).timestamp()
    except Exception:
        return time.time()


def _open_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(STATE_DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS intents (
            id TEXT PRIMARY KEY,
            builder_id TEXT NOT NULL,
            description TEXT NOT NULL,
            deadline TEXT,
            revenue_target REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'active',
            progress REAL NOT NULL DEFAULT 0,
            declared_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_signal_at TEXT NOT NULL,
            last_signal_event TEXT,
            last_signal_value REAL NOT NULL DEFAULT 0,
            drift_score REAL NOT NULL DEFAULT 0,
            intervention_count INTEGER NOT NULL DEFAULT 0,
            last_intervention_at TEXT,
            last_evaluated_tick INTEGER NOT NULL DEFAULT 0,
            referral_source TEXT NOT NULL DEFAULT '',
            revenue_usd REAL NOT NULL DEFAULT 0,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_intents_builder_id ON intents (builder_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_intents_status ON intents (status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_intents_last_evaluated_tick ON intents (last_evaluated_tick)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS drift_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            intent_id TEXT NOT NULL,
            builder_id TEXT NOT NULL,
            tick_n INTEGER NOT NULL,
            drift_score REAL NOT NULL,
            drift_delta REAL NOT NULL,
            category TEXT NOT NULL,
            silence_seconds REAL NOT NULL,
            intervention_sent INTEGER NOT NULL DEFAULT 0,
            intervention_message TEXT,
            created_at TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_drift_events_intent_tick ON drift_events (intent_id, tick_n DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_drift_events_builder_tick ON drift_events (builder_id, tick_n DESC)")
    return conn


@dataclass
class DriftIntent:
    id: str
    builder_id: str
    description: str
    deadline: str
    revenue_target: float
    status: str
    progress: float
    declared_at: str
    updated_at: str
    last_signal_at: str
    last_signal_event: str
    last_signal_value: float
    drift_score: float
    intervention_count: int
    last_intervention_at: str | None
    last_evaluated_tick: int
    referral_source: str
    revenue_usd: float
    metadata: dict[str, Any]

    @property
    def creator(self) -> str:
        return self.builder_id

    @property
    def project_id(self) -> str:
        return self.id

    @property
    def intent(self) -> str:
        return self.description

    @property
    def created_at_ts(self) -> float:
        return _parse_ts(self.declared_at)

    @property
    def last_signal_ts(self) -> float:
        return _parse_ts(self.last_signal_at)

    @property
    def signal_log(self) -> list[dict[str, Any]]:
        return list(self.metadata.get("signal_log") or [])

    @property
    def interventions(self) -> list[dict[str, Any]]:
        return list(self.metadata.get("interventions") or [])

    def convergence_pct(self) -> float:
        if self.revenue_target > 0:
            revenue_progress = min(1.0, self.revenue_usd / max(self.revenue_target, 1.0))
            return round(((self.progress * 0.7) + (revenue_progress * 0.3)) * 100.0, 2)
        return round(self.progress * 100.0, 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.id,
            "creator": self.builder_id,
            "intent": self.description,
            "referral_source": self.referral_source,
            "created_at": self.created_at_ts,
            "declared_at": self.declared_at,
            "deadline": self.deadline,
            "revenue_target": round(self.revenue_target, 2),
            "last_signal": self.last_signal_ts,
            "last_signal_at": self.last_signal_at,
            "last_signal_event": self.last_signal_event,
            "signal_log": self.signal_log[-MAX_SIGNAL_LOG:],
            "drift_score": round(self.drift_score, 4),
            "interventions": self.interventions[-MAX_INTERVENTIONS:],
            "revenue_usd": round(self.revenue_usd, 2),
            "status": self.status,
            "progress": round(self.progress, 4),
            "intervention_count": self.intervention_count,
            "last_intervention_at": self.last_intervention_at,
            "last_evaluated_tick": self.last_evaluated_tick,
            "convergence_pct": self.convergence_pct(),
            "maze_layer": self.metadata.get("maze_layer", "declaration"),
        }


def _row_to_intent(row: sqlite3.Row) -> DriftIntent:
    try:
        metadata = json.loads(row["metadata_json"] or "{}")
    except Exception:
        metadata = {}
    return DriftIntent(
        id=row["id"],
        builder_id=row["builder_id"],
        description=row["description"],
        deadline=row["deadline"] or "",
        revenue_target=float(row["revenue_target"] or 0.0),
        status=row["status"] or "active",
        progress=float(row["progress"] or 0.0),
        declared_at=row["declared_at"],
        updated_at=row["updated_at"],
        last_signal_at=row["last_signal_at"],
        last_signal_event=row["last_signal_event"] or "",
        last_signal_value=float(row["last_signal_value"] or 0.0),
        drift_score=float(row["drift_score"] or 0.0),
        intervention_count=int(row["intervention_count"] or 0),
        last_intervention_at=row["last_intervention_at"],
        last_evaluated_tick=int(row["last_evaluated_tick"] or 0),
        referral_source=row["referral_source"] or "",
        revenue_usd=float(row["revenue_usd"] or 0.0),
        metadata=metadata,
    )


class DriftEngine:
    def __init__(self, cadence_ticks: int = DRIFT_EVERY_TICKS):
        self.cadence_ticks = max(1, int(cadence_ticks))
        self._sync_json()

    def _fetch_intent_row(self, intent_id: str) -> sqlite3.Row | None:
        with _LOCK, _open_conn() as conn:
            return conn.execute("SELECT * FROM intents WHERE id = ?", (intent_id,)).fetchone()

    def get_intent(self, intent_id: str) -> DriftIntent | None:
        row = self._fetch_intent_row(intent_id)
        return _row_to_intent(row) if row else None

    def list_intents(self) -> list[DriftIntent]:
        with _LOCK, _open_conn() as conn:
            rows = conn.execute("SELECT * FROM intents ORDER BY declared_at DESC").fetchall()
        return [_row_to_intent(row) for row in rows]

    @property
    def projects(self) -> dict[str, DriftIntent]:
        return {intent.id: intent for intent in self.list_intents()}

    def declare_intent(
        self,
        builder_id: str,
        description: str,
        deadline: str = "",
        revenue_target: float = 0.0,
        *,
        referral_source: str = "ecosystem",
        intent_id: str | None = None,
    ) -> DriftIntent:
        now = _utc_now()
        resolved_id = intent_id or str(uuid.uuid4())
        metadata = {
            "signal_log": [{"ts": now, "event": "intent_declared", "value": 1.0}],
            "interventions": [],
            "maze_layer": "declaration",
        }
        with _LOCK, _open_conn() as conn:
            conn.execute(
                """
                INSERT INTO intents (
                    id, builder_id, description, deadline, revenue_target, status, progress,
                    declared_at, updated_at, last_signal_at, last_signal_event, last_signal_value,
                    drift_score, intervention_count, last_intervention_at, last_evaluated_tick,
                    referral_source, revenue_usd, metadata_json
                ) VALUES (?, ?, ?, ?, ?, 'active', 0, ?, ?, ?, ?, ?, 0, 0, NULL, 0, ?, 0, ?)
                """,
                (
                    resolved_id,
                    builder_id,
                    description,
                    deadline,
                    float(revenue_target or 0.0),
                    now,
                    now,
                    now,
                    "intent_declared",
                    1.0,
                    referral_source,
                    json.dumps(metadata, ensure_ascii=True),
                ),
            )
        self._sync_json()
        return self.get_intent(resolved_id)

    def _write_intent(self, intent: DriftIntent) -> None:
        with _LOCK, _open_conn() as conn:
            conn.execute(
                """
                UPDATE intents
                SET builder_id = ?, description = ?, deadline = ?, revenue_target = ?, status = ?, progress = ?,
                    updated_at = ?, last_signal_at = ?, last_signal_event = ?, last_signal_value = ?,
                    drift_score = ?, intervention_count = ?, last_intervention_at = ?, last_evaluated_tick = ?,
                    referral_source = ?, revenue_usd = ?, metadata_json = ?
                WHERE id = ?
                """,
                (
                    intent.builder_id,
                    intent.description,
                    intent.deadline,
                    float(intent.revenue_target),
                    intent.status,
                    float(intent.progress),
                    intent.updated_at,
                    intent.last_signal_at,
                    intent.last_signal_event,
                    float(intent.last_signal_value),
                    float(intent.drift_score),
                    int(intent.intervention_count),
                    intent.last_intervention_at,
                    int(intent.last_evaluated_tick),
                    intent.referral_source,
                    float(intent.revenue_usd),
                    json.dumps(intent.metadata, ensure_ascii=True),
                    intent.id,
                ),
            )

    def _append_signal(self, intent: DriftIntent, event: str, value: float = 1.0) -> DriftIntent:
        now = _utc_now()
        signal_log = list(intent.metadata.get("signal_log") or [])
        signal_log.append({"ts": now, "event": event, "value": float(value)})
        intent.metadata["signal_log"] = signal_log[-MAX_SIGNAL_LOG:]
        intent.last_signal_at = now
        intent.last_signal_event = event
        intent.last_signal_value = float(value)
        intent.updated_at = now
        self._write_intent(intent)
        self._sync_json()
        return intent

    def record_signal(self, intent_id: str, event: str, value: float = 1.0) -> DriftIntent | None:
        intent = self.get_intent(intent_id)
        if not intent:
            return None
        return self._append_signal(intent, event, value)

    def update_progress(self, intent_id: str, progress: float, *, status: str | None = None) -> DriftIntent | None:
        intent = self.get_intent(intent_id)
        if not intent:
            return None
        intent.progress = _clamp(progress)
        if status:
            intent.status = status
        elif intent.progress >= 1.0:
            intent.status = "completed"
        elif intent.progress > 0:
            intent.status = "active"
        intent.updated_at = _utc_now()
        self._write_intent(intent)
        return self.record_signal(intent_id, "progress_update", intent.progress)

    def record_revenue(self, intent_id: str, amount_usd: float, source: str = "manual") -> DriftIntent | None:
        intent = self.get_intent(intent_id)
        if not intent:
            return None
        intent.revenue_usd = round(intent.revenue_usd + float(amount_usd or 0.0), 2)
        intent.updated_at = _utc_now()
        self._write_intent(intent)
        return self.record_signal(intent_id, f"revenue:{source}", float(amount_usd or 0.0))

    def _activity_gap(self, intent: DriftIntent, now_ts: float) -> float:
        recent_signals = 0
        for signal in intent.signal_log[-MAX_SIGNAL_LOG:]:
            age = now_ts - _parse_ts(signal.get("ts"))
            if age <= 14 * 86400:
                recent_signals += 1
        return 1.0 - _norm_log(recent_signals, 12.0)

    def _revenue_gap(self, intent: DriftIntent) -> float:
        if intent.revenue_target <= 0:
            return 0.45
        return 1.0 - min(1.0, intent.revenue_usd / max(intent.revenue_target, 1.0))

    def compute_drift(self, intent: DriftIntent, tick_n: int, *, now_ts: float | None = None) -> dict[str, Any]:
        now_ts = now_ts or time.time()
        silence_seconds = max(0.0, now_ts - intent.last_signal_ts)
        if silence_seconds <= SILENCE_SOFT:
            silence_score = (silence_seconds / SILENCE_SOFT) * DRIFT_WARN
        elif silence_seconds <= SILENCE_HARD:
            ratio = (silence_seconds - SILENCE_SOFT) / (SILENCE_HARD - SILENCE_SOFT)
            silence_score = DRIFT_WARN + ratio * (DRIFT_CRITICAL - DRIFT_WARN)
        else:
            ratio = min(1.0, (silence_seconds - SILENCE_HARD) / (SILENCE_MAX - SILENCE_HARD))
            silence_score = DRIFT_CRITICAL + ratio * (1.0 - DRIFT_CRITICAL)

        age_days = max(0.0, (now_ts - intent.created_at_ts) / 86400.0)
        grace_factor = 0.55 if age_days < 1.0 else 0.72 if age_days < 3.0 else 1.0
        progress_gap = 1.0 - _clamp(intent.progress)
        revenue_gap = self._revenue_gap(intent)
        activity_gap = self._activity_gap(intent, now_ts)
        drift_score = _clamp(
            ((silence_score * 0.46) + (progress_gap * 0.22) + (revenue_gap * 0.16) + (activity_gap * 0.16))
            * grace_factor
        )
        if drift_score >= DRIFT_CRITICAL:
            category = "critical"
            status = "dark"
        elif drift_score >= DRIFT_INTERVENE:
            category = "intervene"
            status = "drifting"
        elif drift_score >= DRIFT_WARN:
            category = "watch"
            status = "active"
        else:
            category = "anchored"
            status = "active"
        return {
            "tick": int(tick_n),
            "drift_score": round(drift_score, 4),
            "category": category,
            "status": status,
            "silence_seconds": round(silence_seconds, 2),
            "components": {
                "silence": round(_clamp(silence_score), 4),
                "progress_gap": round(progress_gap, 4),
                "revenue_gap": round(revenue_gap, 4),
                "activity_gap": round(activity_gap, 4),
                "grace_factor": round(grace_factor, 4),
            },
        }

    def _should_intervene(self, intent: DriftIntent, drift_score: float, now_ts: float) -> bool:
        if drift_score < DRIFT_INTERVENE:
            return False
        if not intent.last_intervention_at:
            return True
        since_last = now_ts - _parse_ts(intent.last_intervention_at)
        last_drift = float(intent.metadata.get("last_intervention_drift") or 0.0)
        if since_last >= INTERVENTION_COOLDOWN_SECONDS:
            return True
        return drift_score >= last_drift + 0.08

    def _log_drift_event(
        self,
        intent: DriftIntent,
        tick_n: int,
        drift_score: float,
        drift_delta: float,
        category: str,
        silence_seconds: float,
        intervention_message: str = "",
    ) -> None:
        with _LOCK, _open_conn() as conn:
            conn.execute(
                """
                INSERT INTO drift_events (
                    intent_id, builder_id, tick_n, drift_score, drift_delta, category,
                    silence_seconds, intervention_sent, intervention_message, created_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    intent.id,
                    intent.builder_id,
                    int(tick_n),
                    float(drift_score),
                    float(drift_delta),
                    category,
                    float(silence_seconds),
                    1 if intervention_message else 0,
                    intervention_message,
                    _utc_now(),
                    json.dumps({"status": intent.status}, ensure_ascii=True),
                ),
            )

    def _apply_intervention(
        self,
        intent: DriftIntent,
        drift_report: dict[str, Any],
        *,
        voice: Any | None,
        snapshot: dict[str, Any] | None,
    ) -> str:
        if not voice:
            return ""
        silence_days = round(float(drift_report["silence_seconds"]) / 86400.0, 1)
        severity = "critical" if drift_report["drift_score"] >= DRIFT_CRITICAL else "drifting"
        return voice.intervention_message(
            builder_id=intent.builder_id,
            intent=intent.description,
            drift_score=float(drift_report["drift_score"]),
            silence_days=silence_days,
            severity=severity,
            snapshot=snapshot,
        )

    def _sync_json(self) -> None:
        intents = self.list_intents()
        payload = {
            "saved_at": _utc_now(),
            "projects": {intent.id: intent.to_dict() for intent in intents},
        }
        write_json(PIKKAIO_JSON_PATH, payload)

    def summary(self) -> dict[str, Any]:
        intents = self.list_intents()
        total_revenue = round(sum(intent.revenue_usd for intent in intents), 2)
        by_status: dict[str, list[str]] = {}
        for intent in intents:
            by_status.setdefault(intent.status, []).append(intent.id)
        top_drifters = sorted(
            (
                {"id": intent.id, "creator": intent.builder_id, "drift": round(intent.drift_score, 4)}
                for intent in intents
                if intent.drift_score >= DRIFT_WARN
            ),
            key=lambda item: item["drift"],
            reverse=True,
        )[:MAX_TOP_DRIFTERS]
        return {
            "projects_total": len(intents),
            "project_ids": [intent.id for intent in intents],
            "by_status": by_status,
            "drifting": sum(1 for intent in intents if intent.drift_score >= DRIFT_INTERVENE),
            "critical": sum(1 for intent in intents if intent.drift_score >= DRIFT_CRITICAL),
            "total_revenue": total_revenue,
            "top_drifters": top_drifters,
            "interventions_count": sum(intent.intervention_count for intent in intents),
        }

    def tick(self, tick_num: int, drives: dict[str, float] | None = None, *, voice: Any | None = None, snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
        intents = self.list_intents()
        interventions: list[dict[str, Any]] = []
        drive_deltas = {"serve": 0.0, "connect": 0.0}
        now_ts = time.time()
        projects_total = len(intents)
        drifting = 0

        for intent in intents:
            if intent.last_evaluated_tick and (tick_num - intent.last_evaluated_tick) < self.cadence_ticks:
                if intent.drift_score >= DRIFT_INTERVENE:
                    drifting += 1
                continue

            report = self.compute_drift(intent, tick_num, now_ts=now_ts)
            previous_drift = float(intent.drift_score or 0.0)
            intent.drift_score = float(report["drift_score"])
            intent.status = report["status"]
            intent.last_evaluated_tick = int(tick_num)
            intent.updated_at = _utc_now()
            if intent.drift_score >= DRIFT_INTERVENE:
                drifting += 1

            message = ""
            if self._should_intervene(intent, intent.drift_score, now_ts):
                message = self._apply_intervention(intent, report, voice=voice, snapshot=snapshot)
                if message:
                    intervention_entry = {
                        "tick": int(tick_num),
                        "ts": _utc_now(),
                        "drift": round(intent.drift_score, 4),
                        "message": message,
                    }
                    logs = list(intent.metadata.get("interventions") or [])
                    logs.append(intervention_entry)
                    intent.metadata["interventions"] = logs[-MAX_INTERVENTIONS:]
                    intent.metadata["last_intervention_drift"] = float(intent.drift_score)
                    intent.last_intervention_at = intervention_entry["ts"]
                    intent.intervention_count += 1
                    interventions.append({"project": intent.id, "creator": intent.builder_id, **intervention_entry})

            self._write_intent(intent)
            self._log_drift_event(
                intent,
                tick_num,
                intent.drift_score,
                round(intent.drift_score - previous_drift, 4),
                report["category"],
                float(report["silence_seconds"]),
                intervention_message=message,
            )
            if intent.drift_score >= DRIFT_INTERVENE:
                drive_deltas["serve"] += intent.drift_score * 0.08
                drive_deltas["connect"] += intent.drift_score * 0.05

        self._sync_json()
        total_revenue = round(sum(intent.revenue_usd for intent in self.list_intents()), 2)
        return {
            "tick": int(tick_num),
            "projects_total": projects_total,
            "project_ids": [intent.id for intent in intents],
            "drifting": drifting,
            "critical": sum(1 for intent in intents if intent.drift_score >= DRIFT_CRITICAL),
            "total_revenue": total_revenue,
            "interventions": interventions,
            "interventions_count": sum(intent.intervention_count for intent in intents),
            "drive_deltas": drive_deltas,
        }


def get_drift_engine() -> DriftEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = DriftEngine()
    return _ENGINE
