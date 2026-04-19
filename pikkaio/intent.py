from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from greg_local_memory import LocalMemory


class Intent:
    def __init__(
        self,
        user_id: str,
        description: str,
        deadline: str,
        revenue_target: float,
        *,
        status: str = "active",
        progress: float = 0.0,
        created_at: str | None = None,
        intent_id: str | None = None,
    ) -> None:
        self.id = intent_id or str(uuid.uuid4())
        self.user_id = user_id
        self.description = description
        self.deadline = deadline
        self.revenue_target = float(revenue_target)
        self.status = status
        self.progress = float(progress)
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()

    def dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "description": self.description,
            "deadline": self.deadline,
            "revenue_target": self.revenue_target,
            "status": self.status,
            "progress": self.progress,
            "created_at": self.created_at,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "Intent":
        return cls(
            user_id=str(payload.get("user_id", "unknown")),
            description=str(payload.get("description", "")),
            deadline=str(payload.get("deadline", "")),
            revenue_target=float(payload.get("revenue_target", 0.0) or 0.0),
            status=str(payload.get("status", "active") or "active"),
            progress=float(payload.get("progress", 0.0) or 0.0),
            created_at=str(payload.get("created_at") or datetime.now(timezone.utc).isoformat()),
            intent_id=str(payload.get("id") or str(uuid.uuid4())),
        )


class IntentEngine:
    def __init__(self, memory: LocalMemory):
        self.memory = memory

    def _source(self, intent_id: str) -> str:
        return f"intent_{intent_id}"

    def _load_intent(self, intent_id: str) -> Intent | None:
        rows = self.memory.latest_by_source(self._source(intent_id), limit=1)
        if not rows:
            return None
        try:
            payload = json.loads(rows[0]["content"])
        except json.JSONDecodeError:
            return None
        return Intent.from_payload(payload)

    def declare_intent(self, user_id: str, desc: str, deadline: str, target: float) -> Intent:
        intent = Intent(user_id, desc, deadline, target)
        self.memory.add(self._source(intent.id), intent.dict(), {"kind": "intent", "user_id": user_id})
        return intent

    def update_progress(self, intent_id: str, progress: float, *, status: str | None = None) -> Intent | None:
        intent = self._load_intent(intent_id)
        if intent is None:
            return None
        intent.progress = max(0.0, min(1.0, float(progress)))
        if status:
            intent.status = status
        elif intent.progress >= 1.0:
            intent.status = "completed"
        self.memory.add(self._source(intent.id), intent.dict(), {"kind": "intent", "user_id": intent.user_id})
        return intent

    def get_active_intents(self, user_id: str) -> list[dict[str, Any]]:
        intents: dict[str, Intent] = {}
        for row in self.memory.records_by_prefix("intent_", limit=200):
            try:
                payload = json.loads(row["content"])
            except json.JSONDecodeError:
                continue
            intent = Intent.from_payload(payload)
            if intent.id in intents:
                continue
            if intent.user_id != user_id or intent.status != "active":
                continue
            intents[intent.id] = intent
        return [intent.dict() for intent in sorted(intents.values(), key=lambda item: item.created_at, reverse=True)]

    def completion_rate(self, user_id: str | None = None) -> float:
        latest: dict[str, Intent] = {}
        for row in self.memory.records_by_prefix("intent_", limit=500):
            try:
                payload = json.loads(row["content"])
            except json.JSONDecodeError:
                continue
            intent = Intent.from_payload(payload)
            if intent.id not in latest and (user_id is None or intent.user_id == user_id):
                latest[intent.id] = intent
        if not latest:
            return 0.0
        completed = sum(1 for intent in latest.values() if intent.status == "completed")
        return round(completed / len(latest), 4)
