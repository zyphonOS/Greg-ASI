from __future__ import annotations

import logging
import pickle
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.utils import data_path, ensure_directory


logger = logging.getLogger(__name__)
RL_DB_PATH = data_path("greg_memory.db")
RL_MODEL_PATH = data_path("rl_model.pkl")
CHROMA_PATH = data_path("chroma_intents")
COLLECTION_NAME = "intent_outcomes_examples"

_model_bundle: dict[str, Any] | None = None
_client = None
_collection = None
_model_lock = threading.Lock()
_last_trained_bucket = -1


@dataclass
class IntentOutcome:
    intent_id: str
    description: str
    generated_code: str
    success: bool
    execution_time: float
    user_feedback: str | None
    drift_change: float
    revenue_generated: float
    reward: float
    created_at: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conn() -> sqlite3.Connection:
    ensure_directory(Path(RL_DB_PATH).parent)
    conn = sqlite3.connect(RL_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_rl_store() -> None:
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS intent_outcomes (
                intent_id TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                generated_code TEXT,
                success INTEGER NOT NULL,
                execution_time REAL NOT NULL,
                user_feedback TEXT,
                drift_change REAL NOT NULL,
                revenue_generated REAL NOT NULL,
                reward REAL NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_intent_outcomes_success ON intent_outcomes(success)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_intent_outcomes_created_at ON intent_outcomes(created_at)")
    load_model()
    _ensure_vector_store()


def _ensure_vector_store():
    global _client, _collection
    if _collection is not None:
        return _collection
    try:
        import chromadb

        ensure_directory(Path(CHROMA_PATH))
        _client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        _collection = _client.get_or_create_collection(name=COLLECTION_NAME)
    except Exception as exc:
        logger.warning("Chroma vector store unavailable: %s", exc)
        _collection = None
    return _collection


def _feedback_signal(feedback: str | None) -> float:
    normalized = str(feedback or "").strip().lower()
    if normalized in {"like", "positive", "upvote", "good"}:
        return 1.0
    if normalized in {"dislike", "negative", "downvote", "bad"}:
        return -1.0
    return 0.0


def compute_reward(*, success: bool, user_feedback: str | None, revenue_generated: float) -> float:
    reward = 1.0 if success else -1.0
    reward += _feedback_signal(user_feedback)
    reward += float(revenue_generated or 0.0) * 0.01
    return round(reward, 4)


def record_intent_outcome(
    *,
    intent_id: str,
    description: str,
    generated_code: str,
    success: bool,
    execution_time: float,
    user_feedback: str | None = None,
    drift_change: float = 0.0,
    revenue_generated: float = 0.0,
) -> IntentOutcome:
    reward = compute_reward(success=success, user_feedback=user_feedback, revenue_generated=revenue_generated)
    outcome = IntentOutcome(
        intent_id=str(intent_id),
        description=str(description or "").strip(),
        generated_code=str(generated_code or ""),
        success=bool(success),
        execution_time=round(float(execution_time or 0.0), 4),
        user_feedback=str(user_feedback or "").strip().lower() or None,
        drift_change=round(float(drift_change or 0.0), 6),
        revenue_generated=round(float(revenue_generated or 0.0), 4),
        reward=reward,
        created_at=_utc_now(),
    )
    with _conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO intent_outcomes (
                intent_id, description, generated_code, success, execution_time,
                user_feedback, drift_change, revenue_generated, reward, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                outcome.intent_id,
                outcome.description,
                outcome.generated_code,
                int(outcome.success),
                outcome.execution_time,
                outcome.user_feedback,
                outcome.drift_change,
                outcome.revenue_generated,
                outcome.reward,
                outcome.created_at,
            ),
        )
    _index_success_example(outcome)
    return outcome


def update_intent_feedback(intent_id: str, feedback: str) -> dict[str, Any] | None:
    normalized = str(feedback or "").strip().lower()
    with _conn() as conn:
        row = conn.execute("SELECT * FROM intent_outcomes WHERE intent_id = ?", (str(intent_id),)).fetchone()
        if not row:
            return None
        reward = compute_reward(
            success=bool(int(row["success"])),
            user_feedback=normalized,
            revenue_generated=float(row["revenue_generated"] or 0.0),
        )
        conn.execute(
            "UPDATE intent_outcomes SET user_feedback = ?, reward = ? WHERE intent_id = ?",
            (normalized, reward, str(intent_id)),
        )
        updated = conn.execute("SELECT * FROM intent_outcomes WHERE intent_id = ?", (str(intent_id),)).fetchone()
    payload = dict(updated) if updated else None
    if payload:
        _index_success_example(IntentOutcome(**{
            "intent_id": payload["intent_id"],
            "description": payload["description"],
            "generated_code": payload["generated_code"] or "",
            "success": bool(int(payload["success"])),
            "execution_time": float(payload["execution_time"] or 0.0),
            "user_feedback": payload["user_feedback"],
            "drift_change": float(payload["drift_change"] or 0.0),
            "revenue_generated": float(payload["revenue_generated"] or 0.0),
            "reward": float(payload["reward"] or 0.0),
            "created_at": payload["created_at"],
        }))
    return payload


def _index_success_example(outcome: IntentOutcome) -> None:
    collection = _ensure_vector_store()
    if collection is None:
        return
    if not outcome.success or outcome.reward <= 0:
        return
    document = outcome.description
    generated_excerpt = outcome.generated_code[:2000]
    try:
        collection.upsert(
            ids=[outcome.intent_id],
            documents=[document],
            metadatas=[
                {
                    "reward": float(outcome.reward),
                    "created_at": outcome.created_at,
                    "generated_code": generated_excerpt,
                    "revenue_generated": float(outcome.revenue_generated),
                }
            ],
        )
    except Exception as exc:
        logger.warning("Unable to index intent example in Chroma: %s", exc)


def retrieve_similar_examples(description: str, *, limit: int = 3) -> list[str]:
    collection = _ensure_vector_store()
    if collection is None:
        return []
    clean_description = str(description or "").strip()
    if not clean_description:
        return []
    try:
        result = collection.query(query_texts=[clean_description], n_results=max(1, int(limit)))
    except Exception as exc:
        logger.warning("Chroma query failed: %s", exc)
        return []

    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    examples: list[str] = []
    for document, metadata in zip(documents, metadatas):
        if not document:
            continue
        generated_code = str((metadata or {}).get("generated_code") or "").strip()
        reward = float((metadata or {}).get("reward") or 0.0)
        examples.append(
            f"Intent: {document}\nReward: {reward:.2f}\nWinning pattern: {generated_code[:400]}"
        )
    return examples


def augment_prompt_with_examples(prompt: str) -> str:
    clean_prompt = str(prompt or "").strip()
    if not clean_prompt:
        return clean_prompt
    examples = retrieve_similar_examples(clean_prompt, limit=3)
    if not examples:
        return clean_prompt
    joined = "\n\n---\n\n".join(examples)
    return f"You succeeded in similar tasks:\n{joined}\n\nCurrent task:\n{clean_prompt}"


def _load_rows() -> list[sqlite3.Row]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT intent_id, description, success
            FROM intent_outcomes
            ORDER BY created_at DESC
            """
        ).fetchall()
    return rows


def train_model() -> dict[str, Any]:
    rows = _load_rows()
    texts = [str(row["description"]) for row in rows if str(row["description"]).strip()]
    labels = [int(row["success"]) for row in rows if str(row["description"]).strip()]
    if len(texts) < 4 or len(set(labels)) < 2:
        return {"ok": False, "reason": "not enough labelled data"}

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
    except Exception as exc:
        return {"ok": False, "reason": f"scikit-learn unavailable: {exc}"}

    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_features=2000)
    X = vectorizer.fit_transform(texts)
    model = LogisticRegression(max_iter=1000)
    model.fit(X, labels)
    bundle = {
        "vectorizer": vectorizer,
        "model": model,
        "trained_at": _utc_now(),
        "samples": len(texts),
    }
    ensure_directory(Path(RL_MODEL_PATH).parent)
    with open(RL_MODEL_PATH, "wb") as handle:
        pickle.dump(bundle, handle)
    with _model_lock:
        global _model_bundle
        _model_bundle = bundle
    return {"ok": True, "samples": len(texts), "trained_at": bundle["trained_at"]}


def load_model() -> None:
    global _model_bundle
    if not Path(RL_MODEL_PATH).exists():
        _model_bundle = None
        return
    try:
        with open(RL_MODEL_PATH, "rb") as handle:
            _model_bundle = pickle.load(handle)
    except Exception as exc:
        logger.warning("Unable to load RL model: %s", exc)
        _model_bundle = None


def predict_intent_success(description: str) -> float:
    with _model_lock:
        bundle = _model_bundle
    if not bundle:
        return 0.5
    try:
        vectorizer = bundle["vectorizer"]
        model = bundle["model"]
        probabilities = model.predict_proba(vectorizer.transform([str(description or "")]))
        return round(float(probabilities[0][1]), 4)
    except Exception as exc:
        logger.warning("RL model prediction failed: %s", exc)
        return 0.5


def latest_intent_outcomes(limit: int = 25) -> list[dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM intent_outcomes
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
    return [dict(row) for row in rows]


def start_rl_background_loop(greg) -> None:
    init_rl_store()

    def worker() -> None:
        global _last_trained_bucket
        while True:
            try:
                tick = int(getattr(getattr(greg, "world", None), "tick", 0))
                bucket = tick // 100
                if bucket > _last_trained_bucket and tick >= 100:
                    result = train_model()
                    if result.get("ok"):
                        _last_trained_bucket = bucket
            except Exception as exc:
                logger.warning("RL background training failed: %s", exc)
            time.sleep(5.0)

    thread = threading.Thread(target=worker, name="greg-rl-loop", daemon=True)
    thread.start()
