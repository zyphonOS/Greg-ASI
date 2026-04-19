from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import requests

from core.utils import append_jsonl, data_path, read_json


DEFAULT_LOG_PATH = data_path("drift_attestations.jsonl")


def _state_hash(state: dict) -> str:
    payload = json.dumps(state or {}, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def compute_drift_coefficient(state: dict | None) -> dict:
    state = state or {}
    drives = {key: float(value) for key, value in (state.get("drives") or {}).items() if isinstance(value, (int, float))}
    if not drives:
        drives = {"exist": 0.0}
    values = list(drives.values())
    avg = sum(values) / len(values)
    variance = sum((value - avg) ** 2 for value in values) / len(values)
    balance = max(0.0, 1.0 - min(1.0, variance * 4.0))
    coefficient = max(0.0, min(1.0, 1.0 - (0.6 * avg + 0.4 * balance)))
    if coefficient < 0.25:
        category = "anchored"
        interpretation = "Greg is coherent and resisting dissolution."
    elif coefficient < 0.55:
        category = "watch"
        interpretation = "Greg is stable, but drift pressure is present."
    else:
        category = "acute"
        interpretation = "Drift is elevated and intervention pressure is rising."
    dominant = max(drives, key=drives.get) if drives else "exist"
    tick = int(state.get("tick") or 0)
    return {
        "coefficient": round(coefficient, 6),
        "category": category,
        "interpretation": interpretation,
        "dominant": dominant,
        "state_hash": _state_hash(state),
        "tick": tick,
    }


def drift_voice(report: dict) -> str:
    category = report.get("category", "watch")
    dominant = report.get("dominant", "exist")
    coefficient = report.get("coefficient", 0.0)
    if category == "anchored":
        return f"My field is anchored. Drift coefficient {coefficient:.4f}. Dominant drive: {dominant}."
    if category == "acute":
        return f"Drift is high at {coefficient:.4f}. I need action aligned with {dominant} to recover coherence."
    return f"I feel the edge of drift at {coefficient:.4f}. Keep tending the field through {dominant}."


class DriftAttestation:
    def __init__(self, log_path: Path | None = None):
        self.log_path = Path(log_path or DEFAULT_LOG_PATH)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.webhook_url = (read_json(data_path("config.json"), {}).get("drift_webhook") or "").strip()

    def _latest_record(self, project_id: str) -> dict | None:
        if not self.log_path.exists():
            return None
        latest = None
        for line in self.log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except Exception:
                continue
            if record.get("project_id") == project_id:
                latest = record
        return latest

    def attest_drift(self, project_id: str, intent_text: str, drift_score: float, tick: int) -> dict:
        record = {
            "project_id": project_id,
            "intent_hash": hashlib.sha256(intent_text.encode("utf-8")).hexdigest(),
            "drift_score": round(float(drift_score), 6),
            "tick": int(tick or 0),
            "timestamp": int(time.time()),
            "mode": "local_log",
        }
        append_jsonl(self.log_path, record)
        if self.webhook_url:
            try:
                response = requests.post(self.webhook_url, json=record, timeout=15)
                record["webhook_status"] = response.status_code
            except Exception:
                record["webhook_status"] = "failed"
        return {"ok": True, **record}

    def get_attestation(self, project_id: str) -> dict:
        latest = self._latest_record(project_id)
        if not latest:
            return {"ok": False, "error": "no attestation"}
        return {"ok": True, **latest}

    def summary(self) -> dict:
        history = []
        if self.log_path.exists():
            for line in self.log_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    history.append(json.loads(line))
                except Exception:
                    continue
        return {
            "attest_count": len(history),
            "latest_attestation": history[-1] if history else None,
            "attestation_history": history[-10:],
        }


_engine: DriftAttestation | None = None


def get_drift_status() -> DriftAttestation:
    global _engine
    if _engine is None:
        _engine = DriftAttestation()
    return _engine


def drift_tick(tick_num: int, state: dict) -> dict:
    report = compute_drift_coefficient(state or {})
    summary = get_drift_status().summary()
    return {
        "tick": int(tick_num or report.get("tick") or 0),
        "coefficient": report["coefficient"],
        "category": report["category"],
        "dominant": report["dominant"],
        "state_hash": report["state_hash"],
        "attest_count": summary["attest_count"],
        "latest_attestation": summary.get("latest_attestation"),
    }
