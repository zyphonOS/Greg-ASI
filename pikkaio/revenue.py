from __future__ import annotations

import json
from typing import Any

from constitution_runtime import constitutional_revenue_allocation
from greg_local_memory import LocalMemory


class RevenueTracker:
    def __init__(self, memory: LocalMemory):
        self.memory = memory

    def add_earning(self, user_id: str, amount: float, source: str) -> dict[str, Any]:
        payload = {"user_id": user_id, "amount": float(amount), "source": source}
        self.memory.add(f"revenue_{user_id}", payload, {"kind": "revenue", "user_id": user_id})
        return payload

    def total_earnings(self, user_id: str) -> float:
        total = 0.0
        for row in self.memory.latest_by_source(f"revenue_{user_id}", limit=500):
            try:
                payload = json.loads(row["content"])
                total += float(payload.get("amount", 0.0) or 0.0)
            except Exception:
                continue
        return round(total, 2)

    def aggregate_totals(self) -> dict[str, float]:
        totals: dict[str, float] = {}
        for row in self.memory.records_by_prefix("revenue_", limit=1000):
            try:
                payload = json.loads(row["content"])
                user_id = str(payload.get("user_id", "unknown"))
                totals[user_id] = round(totals.get(user_id, 0.0) + float(payload.get("amount", 0.0) or 0.0), 2)
            except Exception:
                continue
        return totals

    def total_bucket(self, bucket_id: str) -> float:
        total = 0.0
        for row in self.memory.latest_by_source(f"revenue_{bucket_id}", limit=1000):
            try:
                payload = json.loads(row["content"])
                total += float(payload.get("amount", 0.0) or 0.0)
            except Exception:
                continue
        return round(total, 2)

    def allocate_outcome_revenue(self, builder_id: str, amount: float, source: str) -> dict[str, Any]:
        gross_amount = float(amount or 0.0)
        allocation = constitutional_revenue_allocation(
            gross_amount,
            treasury_balance=self.total_bucket("treasury"),
            projected_builder_income=gross_amount * 0.4,
        )

        records = {
            builder_id: {
                "user_id": builder_id,
                "amount": allocation["builder_share"],
                "source": source,
                "bucket": "builder",
                "gross_amount": gross_amount,
            },
            "greg_core": {
                "user_id": "greg_core",
                "amount": allocation["greg_share"],
                "source": source,
                "bucket": "greg",
                "gross_amount": gross_amount,
            },
            "treasury": {
                "user_id": "treasury",
                "amount": allocation["treasury_share"],
                "source": source,
                "bucket": "treasury",
                "gross_amount": gross_amount,
            },
        }

        for bucket_id, payload in records.items():
            self.memory.add(
                f"revenue_{bucket_id}",
                payload,
                {"kind": "revenue", "bucket": payload["bucket"], "source": source},
            )

        return {
            "gross_amount": round(gross_amount, 2),
            "builder_id": builder_id,
            "source": source,
            "allocation": allocation,
        }
