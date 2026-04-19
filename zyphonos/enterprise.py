from __future__ import annotations

import json
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

from greg_local_memory import LocalMemory


class EnterpriseClient:
    def __init__(
        self,
        name: str,
        contact_email: str,
        subscription_tier: str,
        *,
        client_id: str | None = None,
        api_key: str | None = None,
        created_at: str | None = None,
    ) -> None:
        self.id = client_id or str(uuid.uuid4())
        self.name = name
        self.contact_email = contact_email
        self.tier = subscription_tier
        self.api_key = api_key or secrets.token_urlsafe(32)
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()

    def dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "contact_email": self.contact_email,
            "tier": self.tier,
            "api_key": self.api_key,
            "created_at": self.created_at,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "EnterpriseClient":
        return cls(
            name=str(payload.get("name", "")),
            contact_email=str(payload.get("contact_email", "")),
            subscription_tier=str(payload.get("tier", "free")),
            client_id=str(payload.get("id") or str(uuid.uuid4())),
            api_key=str(payload.get("api_key") or secrets.token_urlsafe(32)),
            created_at=str(payload.get("created_at") or datetime.now(timezone.utc).isoformat()),
        )


class ZyphonOS:
    def __init__(self, memory: LocalMemory):
        self.memory = memory
        self.clients: dict[str, EnterpriseClient] = {}
        self._hydrate_clients()

    def _source(self, client_id: str) -> str:
        return f"zyphon_client_{client_id}"

    def _hydrate_clients(self) -> None:
        self.clients.clear()
        for row in self.memory.records_by_prefix("zyphon_client_", limit=500):
            source = row["source"]
            if source in self.clients:
                continue
            try:
                payload = json.loads(row["content"])
            except json.JSONDecodeError:
                continue
            client = EnterpriseClient.from_payload(payload)
            self.clients[client.id] = client

    def register_client(self, name: str, email: str, tier: str) -> EnterpriseClient:
        client = EnterpriseClient(name, email, tier)
        self.clients[client.id] = client
        self.memory.add(self._source(client.id), client.dict(), {"kind": "zyphonos_client", "tier": tier})
        return client

    def verify_api_key(self, api_key: str | None) -> EnterpriseClient | None:
        if not api_key:
            return None
        for client in self.clients.values():
            if client.api_key == api_key:
                return client
        self._hydrate_clients()
        for client in self.clients.values():
            if client.api_key == api_key:
                return client
        return None

    def list_clients(self) -> list[dict[str, Any]]:
        self._hydrate_clients()
        return [client.dict() for client in sorted(self.clients.values(), key=lambda item: item.created_at, reverse=True)]
