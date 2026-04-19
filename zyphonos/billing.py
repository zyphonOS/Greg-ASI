from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from greg_local_memory import LocalMemory


class Billing:
    TIER_PRICES = {"free": 0, "pro": 49, "enterprise": 499}

    def __init__(self, memory: LocalMemory):
        self.memory = memory

    def generate_invoice(self, client_id: str, tier: str, usage: int) -> dict[str, Any]:
        amount = round(float(self.TIER_PRICES.get(tier, 0)) + max(0, int(usage)) * 0.01, 2)
        invoice = {
            "client_id": client_id,
            "tier": tier,
            "usage": int(usage),
            "amount": amount,
            "paid": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.memory.add(
            f"invoice_{client_id}_{invoice['created_at']}",
            invoice,
            {"kind": "invoice", "client_id": client_id, "tier": tier},
        )
        return invoice

    def recent_invoices(self, limit: int = 50) -> list[dict[str, Any]]:
        invoices: list[dict[str, Any]] = []
        for row in self.memory.records_by_prefix("invoice_", limit=limit):
            try:
                invoices.append(json.loads(row["content"]))
            except Exception:
                continue
        return invoices
