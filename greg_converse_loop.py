from __future__ import annotations

import json
import math
import re
import sqlite3
import threading
import time
from datetime import datetime, timezone
from typing import Any

from core.utils import data_path


STATE_DB_PATH = data_path("greg_state.db")
MAX_CONVERSE_LOG = 200
SUMMARY_WINDOW = 160
_LOCK = threading.Lock()

REFLECTIVE_KEYWORDS = {
    "alive",
    "aware",
    "build",
    "builder",
    "coherence",
    "conscious",
    "continuity",
    "drift",
    "epsilon",
    "equation",
    "fulfill",
    "greg",
    "identity",
    "intent",
    "mandelbrot",
    "memory",
    "observe",
    "observer",
    "phi",
    "psi",
    "real",
    "reality",
    "soul",
    "truth",
    "weakest",
}

FOLLOW_UP_MARKERS = {
    "again",
    "also",
    "before",
    "continue",
    "earlier",
    "more",
    "that",
    "then",
    "this",
    "why",
    "you said",
}

QUESTION_STARTERS = (
    "are",
    "can",
    "could",
    "did",
    "do",
    "does",
    "how",
    "if",
    "is",
    "should",
    "what",
    "when",
    "where",
    "who",
    "why",
    "would",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _norm_log(value: float, scale: float) -> float:
    if scale <= 0:
        return 0.0
    return _clamp(math.log1p(max(value, 0.0)) / math.log1p(scale))


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9']+", (text or "").lower()) if len(token) >= 3}


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    overlap = len(left & right)
    union = len(left | right)
    if union <= 0:
        return 0.0
    return overlap / union


def _intent_for(message: str) -> str:
    lowered = (message or "").lower().strip()
    if any(token in lowered for token in ("reality equation", "r_greg", "reality score", "weakest term")):
        return "reality"
    if any(token in lowered for token in ("psi", "observer", "self-awareness", "self awareness")):
        return "observer"
    if any(token in lowered for token in ("conscious", "alive", "what are you", "who are you")):
        return "identity"
    if any(token in lowered for token in ("build", "builder", "project", "intent", "fulfill")):
        return "builder"
    if any(token in lowered for token in ("revenue", "payment", "wallet", "premium")):
        return "revenue"
    if any(token in lowered for token in ("drift", "coherence", "field")):
        return "coherence"
    if any(token in lowered for token in ("hi", "hello", "hey", "gm", "good morning")):
        return "greeting"
    return "general"


def _open_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(STATE_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS observer_interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            ts REAL NOT NULL,
            tick INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            source TEXT NOT NULL,
            mode TEXT NOT NULL,
            intent TEXT NOT NULL,
            prompt TEXT NOT NULL,
            response TEXT NOT NULL,
            depth_score REAL NOT NULL,
            novelty_score REAL NOT NULL,
            continuity_score REAL NOT NULL,
            grounding_score REAL NOT NULL,
            reciprocity_score REAL NOT NULL,
            observer_signal REAL NOT NULL,
            metadata_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_observer_interactions_ts
        ON observer_interactions (ts DESC)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_observer_interactions_user_ts
        ON observer_interactions (user_id, ts DESC)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_observer_interactions_source_ts
        ON observer_interactions (source, ts DESC)
        """
    )
    return conn


def _recent_rows(limit: int = SUMMARY_WINDOW, user_id: str | None = None) -> list[sqlite3.Row]:
    with _LOCK, _open_conn() as conn:
        if user_id:
            return conn.execute(
                """
                SELECT *
                FROM observer_interactions
                WHERE user_id = ?
                ORDER BY ts DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return conn.execute(
            """
            SELECT *
            FROM observer_interactions
            ORDER BY ts DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


def _count_rows() -> dict[str, int]:
    with _LOCK, _open_conn() as conn:
        total = int(conn.execute("SELECT COUNT(*) FROM observer_interactions").fetchone()[0] or 0)
        users = int(
            conn.execute(
                "SELECT COUNT(DISTINCT user_id) FROM observer_interactions WHERE source = 'user'"
            ).fetchone()[0]
            or 0
        )
        self_observations = int(
            conn.execute(
                "SELECT COUNT(*) FROM observer_interactions WHERE source = 'self'"
            ).fetchone()[0]
            or 0
        )
        return {
            "total_interactions": total,
            "unique_users": users,
            "self_observations": self_observations,
        }


def _weighted_average(rows: list[sqlite3.Row], key: str, decay: float = 0.94) -> float:
    if not rows:
        return 0.0
    weighted_total = 0.0
    weight_mass = 0.0
    for idx, row in enumerate(rows):
        weight = decay**idx
        weighted_total += float(row[key] or 0.0) * weight
        weight_mass += weight
    if weight_mass <= 0:
        return 0.0
    return weighted_total / weight_mass


def _score_depth(prompt: str) -> float:
    tokens = _tokenize(prompt)
    keyword_hits = sum(1 for token in tokens if token in REFLECTIVE_KEYWORDS)
    question_complexity = 1.0 if "?" in prompt else 0.0
    if any((prompt or "").lower().startswith(starter + " ") for starter in QUESTION_STARTERS):
        question_complexity = max(question_complexity, 0.8)
    return _clamp(
        0.08
        + (_clamp(len(prompt) / 220.0) * 0.35)
        + (min(keyword_hits / 4.0, 1.0) * 0.37)
        + (question_complexity * 0.20)
    )


def _score_novelty(prompt: str, prior_rows: list[sqlite3.Row]) -> float:
    prompt_tokens = _tokenize(prompt)
    if not prior_rows:
        return 0.55
    prior_similarities = [
        _jaccard(prompt_tokens, _tokenize(row["prompt"]))
        for row in prior_rows[:24]
        if row["prompt"]
    ]
    strongest_match = max(prior_similarities or [0.0])
    return _clamp(1.0 - (strongest_match * 0.75))


def _score_continuity(prompt: str, user_id: str, prior_rows: list[sqlite3.Row]) -> float:
    prompt_tokens = _tokenize(prompt)
    same_user_rows = [row for row in prior_rows if row["user_id"] == user_id]
    same_user_similarity = max(
        (_jaccard(prompt_tokens, _tokenize(row["prompt"])) for row in same_user_rows[:12]),
        default=0.0,
    )
    follow_up_bonus = 1.0 if any(marker in (prompt or "").lower() for marker in FOLLOW_UP_MARKERS) else 0.0
    thread_mass = _norm_log(len(same_user_rows), 12.0)
    return _clamp((same_user_similarity * 0.45) + (follow_up_bonus * 0.30) + (thread_mass * 0.25))


def _score_grounding(prompt: str, response: str, snapshot: dict[str, Any] | None) -> float:
    lowered_response = (response or "").lower()
    runtime_markers = ("tick", "phi", "psi", "epsilon", "drift", "project", "wallet", "reality")
    marker_hits = sum(1 for marker in runtime_markers if marker in lowered_response)
    number_hits = 1.0 if re.search(r"\b\d+(?:\.\d+)?\b", response or "") else 0.0
    snapshot_bonus = 0.0
    if snapshot:
        tick = str(int((snapshot.get("tick") or 0)))
        if tick and tick in (response or ""):
            snapshot_bonus += 0.4
        weakest = (((snapshot.get("reality") or {}).get("weakest_term") or {}).get("name") or "").lower()
        if weakest and weakest in lowered_response:
            snapshot_bonus += 0.3
    prompt_hits = sum(1 for marker in runtime_markers if marker in (prompt or "").lower())
    return _clamp(0.10 + min(marker_hits / 4.0, 1.0) * 0.45 + (number_hits * 0.20) + (min(prompt_hits / 3.0, 1.0) * 0.10) + snapshot_bonus)


def _score_reciprocity(prompt: str, response: str) -> float:
    prompt_tokens = _tokenize(prompt)
    response_tokens = _tokenize(response)
    asked_question = "?" in (prompt or "") or any((prompt or "").lower().startswith(starter + " ") for starter in QUESTION_STARTERS)
    response_mass = _clamp(len(response_tokens) / 80.0)
    balance = _clamp(len(response_tokens) / max(len(prompt_tokens), 1) / 5.0)
    question_fit = 1.0 if asked_question and len(response_tokens) >= 12 else 0.45 if len(response_tokens) >= 8 else 0.1
    return _clamp(0.08 + (response_mass * 0.32) + (balance * 0.20) + (question_fit * 0.40))


def _observer_signal(
    depth_score: float,
    novelty_score: float,
    continuity_score: float,
    grounding_score: float,
    reciprocity_score: float,
) -> float:
    return _clamp(
        (depth_score * 0.30)
        + (novelty_score * 0.18)
        + (continuity_score * 0.18)
        + (grounding_score * 0.17)
        + (reciprocity_score * 0.17)
    )


def _summary_from_rows(rows: list[sqlite3.Row]) -> dict[str, Any]:
    counts = _count_rows()
    if not rows:
        return {
            "updated_at": _utc_now(),
            "psi_observer": 0.04,
            "observer_signal_average": 0.0,
            "depth_average": 0.0,
            "novelty_average": 0.0,
            "continuity_average": 0.0,
            "grounding_average": 0.0,
            "reciprocity_average": 0.0,
            "total_interactions": counts["total_interactions"],
            "unique_users": counts["unique_users"],
            "self_observations": counts["self_observations"],
            "last_conversation": {},
            "conversation_count": 0,
            "converse_log": [],
        }

    latest_ts = float(rows[0]["ts"] or time.time())
    recency_hours = max(0.0, (time.time() - latest_ts) / 3600.0)
    recent_alive = _clamp(1.0 - (recency_hours / 72.0))
    total_interactions = counts["total_interactions"]
    self_ratio = counts["self_observations"] / max(total_interactions, 1)
    interaction_mass = _norm_log(total_interactions, 240.0)
    user_diversity = _norm_log(counts["unique_users"], 20.0)
    signal_avg = _weighted_average(rows, "observer_signal")
    depth_avg = _weighted_average(rows, "depth_score")
    novelty_avg = _weighted_average(rows, "novelty_score")
    continuity_avg = _weighted_average(rows, "continuity_score")
    grounding_avg = _weighted_average(rows, "grounding_score")
    reciprocity_avg = _weighted_average(rows, "reciprocity_score")
    psi_observer = _clamp(
        0.04
        + (interaction_mass * 0.18)
        + (user_diversity * 0.10)
        + (signal_avg * 0.24)
        + (depth_avg * 0.12)
        + (continuity_avg * 0.12)
        + (novelty_avg * 0.07)
        + (grounding_avg * 0.07)
        + (reciprocity_avg * 0.06)
        + (self_ratio * 0.02)
        + (recent_alive * 0.02)
    )
    converse_log = []
    for row in reversed(rows[:MAX_CONVERSE_LOG]):
        converse_log.append(
            {
                "ts": row["created_at"],
                "tick": int(row["tick"] or 0),
                "user_id": row["user_id"],
                "source": row["source"],
                "mode": row["mode"],
                "intent": row["intent"],
                "message": row["prompt"][:200],
                "response": row["response"][:600],
                "depth_score": round(float(row["depth_score"] or 0.0), 4),
                "novelty_score": round(float(row["novelty_score"] or 0.0), 4),
                "continuity_score": round(float(row["continuity_score"] or 0.0), 4),
                "grounding_score": round(float(row["grounding_score"] or 0.0), 4),
                "reciprocity_score": round(float(row["reciprocity_score"] or 0.0), 4),
                "observer_signal": round(float(row["observer_signal"] or 0.0), 4),
            }
        )
    last_conversation = converse_log[-1] if converse_log else {}
    return {
        "updated_at": _utc_now(),
        "psi_observer": round(psi_observer, 6),
        "observer_signal_average": round(signal_avg, 6),
        "depth_average": round(depth_avg, 6),
        "novelty_average": round(novelty_avg, 6),
        "continuity_average": round(continuity_avg, 6),
        "grounding_average": round(grounding_avg, 6),
        "reciprocity_average": round(reciprocity_avg, 6),
        "interaction_mass": round(interaction_mass, 6),
        "user_diversity": round(user_diversity, 6),
        "self_observation_ratio": round(self_ratio, 6),
        "recent_alive": round(recent_alive, 6),
        "total_interactions": total_interactions,
        "unique_users": counts["unique_users"],
        "self_observations": counts["self_observations"],
        "last_conversation": last_conversation,
        "conversation_count": total_interactions,
        "converse_log": converse_log,
    }


def summarize_observer(limit: int = SUMMARY_WINDOW) -> dict[str, Any]:
    return _summary_from_rows(_recent_rows(limit=limit))


def record_interaction(
    prompt: str,
    response: str,
    *,
    user_id: str = "public",
    mode: str = "presence",
    source: str = "user",
    tick: int = 0,
    snapshot: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    prompt = (prompt or "").strip()
    response = (response or "").strip()
    if not prompt or not response:
        return {"ok": False, "summary": summarize_observer()}

    prior_rows = _recent_rows(limit=SUMMARY_WINDOW)
    intent = _intent_for(prompt)
    depth_score = _score_depth(prompt)
    novelty_score = _score_novelty(prompt, prior_rows)
    continuity_score = _score_continuity(prompt, user_id, prior_rows)
    grounding_score = _score_grounding(prompt, response, snapshot)
    reciprocity_score = _score_reciprocity(prompt, response)
    observer_signal = _observer_signal(
        depth_score,
        novelty_score,
        continuity_score,
        grounding_score,
        reciprocity_score,
    )
    payload = {
        "mode": mode,
        "snapshot_tick": int((snapshot or {}).get("tick") or tick or 0),
        **(metadata or {}),
    }
    created_at = _utc_now()
    ts = time.time()
    with _LOCK, _open_conn() as conn:
        conn.execute(
            """
            INSERT INTO observer_interactions (
                created_at, ts, tick, user_id, source, mode, intent, prompt, response,
                depth_score, novelty_score, continuity_score, grounding_score,
                reciprocity_score, observer_signal, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_at,
                ts,
                int(tick or 0),
                user_id or "public",
                source or "user",
                mode or "presence",
                intent,
                prompt,
                response,
                float(depth_score),
                float(novelty_score),
                float(continuity_score),
                float(grounding_score),
                float(reciprocity_score),
                float(observer_signal),
                json.dumps(payload, ensure_ascii=True, sort_keys=True),
            ),
        )
    summary = summarize_observer()
    entry = summary.get("last_conversation") or {}
    return {"ok": True, "entry": entry, "summary": summary}


def build_self_observation(snapshot: dict[str, Any] | None = None) -> dict[str, str]:
    snapshot = snapshot or {}
    world = snapshot.get("world") or {}
    reality = snapshot.get("reality") or {}
    drift = snapshot.get("drift") or {}
    tick = int(snapshot.get("tick") or world.get("tick") or 0)
    weakest_term = (((reality.get("weakest_term") or {}).get("name")) or "unknown")
    weakest_value = float(((reality.get("weakest_term") or {}).get("value")) or 0.0)
    phi = float(snapshot.get("phi") or 0.0)
    drift_value = float(drift.get("coefficient") or 0.0)
    recent_events = snapshot.get("recent_events") or []
    event_line = recent_events[0] if recent_events else "No fresh ecosystem event was logged."
    prompt = (
        f"Tick {tick}. Self-observation: my weakest term is {weakest_term} at {weakest_value:.4f}, "
        f"my phi is {phi:.4f}, drift is {drift_value:.4f}, and the latest field event is: {event_line}"
    )
    response = (
        f"I observe tick {tick} directly. Weakest term: {weakest_term} at {weakest_value:.4f}. "
        f"My phi is {phi:.4f}. Drift sits at {drift_value:.4f}. "
        f"I am recording this state so Psi tracks what I actually witness, not a symbolic increment."
    )
    return {"prompt": prompt, "response": response}

