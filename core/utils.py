from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

from eth_account import Account
from eth_account.messages import encode_defunct


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
AGENTS_DIR = PROJECT_ROOT / "agents"
STATIC_DIR = PROJECT_ROOT / "static"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
_FILE_LOCK = threading.Lock()


def project_path(*parts: str) -> Path:
    return PROJECT_ROOT.joinpath(*parts)


def repo_path(*parts: str) -> Path:
    return project_path(*parts)


def data_path(*parts: str) -> Path:
    return DATA_DIR.joinpath(*parts)


def state_path(*parts: str) -> Path:
    return DATA_DIR.joinpath(*parts)


def agents_path(*parts: str) -> Path:
    return AGENTS_DIR.joinpath(*parts)


def static_path(*parts: str) -> Path:
    return STATIC_DIR.joinpath(*parts)


def templates_path(*parts: str) -> Path:
    return TEMPLATES_DIR.joinpath(*parts)


def ensure_directory(path: Path | str) -> Path:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def ensure_json_file(path: Path | str, default: Any) -> Path:
    target = Path(path)
    ensure_directory(target.parent)
    if not target.exists():
        with target.open("w", encoding="utf-8") as handle:
            json.dump(default, handle, indent=2)
    return target


def read_json(path: Path | str, default: Any) -> Any:
    target = ensure_json_file(path, default)
    with _FILE_LOCK:
        try:
            with target.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError):
            return default


def write_json(path: Path | str, payload: Any) -> None:
    target = Path(path)
    ensure_directory(target.parent)
    temp_path = target.with_suffix(f"{target.suffix}.tmp")
    with _FILE_LOCK:
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        os.replace(temp_path, target)


def append_jsonl(path: Path | str, record: dict[str, Any]) -> None:
    target = Path(path)
    ensure_directory(target.parent)
    with _FILE_LOCK:
        with target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")


class TTLCache:
    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self._store: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            if entry["expires_at"] <= time.time():
                self._store.pop(key, None)
                return None
            return entry["value"]

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> Any:
        ttl = ttl_seconds if ttl_seconds is not None else self.ttl_seconds
        with self._lock:
            self._store[key] = {
                "value": value,
                "expires_at": time.time() + ttl,
            }
        return value

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


def signature_message(nonce: str) -> str:
    return f"HarvestIQ login: {nonce}"


def verify_wallet_signature(address: str, signature: str, nonce: str) -> bool:
    if not address or not signature or not nonce:
        return False
    try:
        message = encode_defunct(text=signature_message(nonce))
        recovered = Account.recover_message(message, signature=signature)
    except Exception:
        return False
    return recovered.lower() == address.lower()
