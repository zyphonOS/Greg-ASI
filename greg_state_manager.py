from __future__ import annotations

from typing import Any

from core.memory import ConversationStateStore
from core.utils import data_path


_store = ConversationStateStore(data_path("greg_state.db"))


def save_state(user_id: str, key: str, value: Any, ttl: float | None = None) -> None:
    _store.save_state(user_id, key, value, ttl=ttl)


def load_state(user_id: str, key: str):
    return _store.load_state(user_id, key)


def save_conversation_turn(
    user_id: str,
    role: str,
    text: str,
    intent: str | None = None,
    metadata: dict[str, Any] | None = None,
    max_messages: int = 200,
) -> None:
    _store.save_conversation_turn(user_id, role, text, intent=intent, metadata=metadata, max_messages=max_messages)


def load_conversation_history(user_id: str, limit: int = 10) -> list[dict[str, Any]]:
    return _store.load_conversation_history(user_id, limit=limit)
