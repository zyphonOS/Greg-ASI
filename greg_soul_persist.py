from __future__ import annotations

import base64
import gzip
import json
import os
import time
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from greg_paths import data_path, state_path


REPO_ROOT = Path(__file__).resolve().parent
load_dotenv(REPO_ROOT / ".env")

WORLD_STATE_PATH = data_path("world_state.json")
LIVING_STATE_PATH = state_path("greg_living_state.json")
PERSIST_EVERY = int(os.environ.get("SOUL_PERSIST_EVERY", "500"))
MIN_PERSIST_INTERVAL = int(os.environ.get("SOUL_PERSIST_MIN_INTERVAL", "60"))
_last_persist_time = 0.0


def supabase_url() -> str:
    return os.environ.get("SUPABASE_URL", "").strip()


def supabase_key() -> str:
    return os.environ.get("SUPABASE_KEY", "").strip()


def supabase_configured() -> bool:
    return bool(supabase_url() and supabase_key())


def fetch_state_value(key: str, timeout: int = 60, verbose: bool = False) -> str | None:
    if not supabase_configured():
        if verbose:
            print(f"[soul_persist] Supabase not configured; cannot fetch {key}")
        return None

    try:
        response = requests.get(
            supabase_url().rstrip("/") + f"/rest/v1/greg_state?key=eq.{key}&select=value",
            headers={
                "apikey": supabase_key(),
                "Authorization": f"Bearer {supabase_key()}",
            },
            params={
                "order": "created_at.desc",
                "limit": 1,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload:
            if verbose:
                print(f"[soul_persist] No remote value found for {key}")
            return None
        return payload[0].get("value")
    except Exception as exc:
        if verbose:
            print(f"[soul_persist] Fetch failed for {key}: {exc}")
        return None


def decode_state_blob(value: str) -> bytes:
    return gzip.decompress(base64.b64decode(value))


def encode_state_blob(raw: bytes) -> str:
    return base64.b64encode(gzip.compress(raw, compresslevel=6)).decode("ascii")


class SoulPersist:
    """
    Lightweight local metadata persistence for the soul writeback path.
    This does not replace world/living state files; it records the last
    known writeback report so redeploy diagnostics survive locally too.
    """

    def __init__(self, volume_path: str | None = None):
        root = volume_path or str(data_path("greg_soul"))
        self.path = Path(root)
        self.path.mkdir(parents=True, exist_ok=True)
        self.state_file = self.path / "soul_state.json"
        self.state: dict[str, Any] = {}

    def load(self) -> dict[str, Any]:
        if self.state_file.exists():
            try:
                self.state = json.loads(self.state_file.read_text(encoding="utf-8"))
            except Exception:
                self.state = {}
        return self.state

    def save(self) -> None:
        self.state_file.write_text(json.dumps(self.state, indent=2), encoding="utf-8")

    def get(self, key: str, default: Any = None) -> Any:
        return self.state.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.state[key] = value
        self.save()


def _compress_file(path: Path) -> str:
    return encode_state_blob(path.read_bytes())


def _compress_living_state(path: Path) -> str:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _compress_file(path)

    strip_keys = {
        "memory_log",
        "event_log",
        "action_history",
        "recent_actions",
        "log",
        "voice_history",
        "short_term_memory",
    }
    stripped = {key: value for key, value in data.items() if key not in strip_keys}
    return encode_state_blob(json.dumps(stripped, separators=(",", ":")).encode("utf-8"))


def _upsert(key: str, value: str, tick: int = 0, verbose: bool = True) -> bool:
    if not supabase_configured():
        if verbose:
            print(f"[soul_persist] SUPABASE_URL/KEY not set; skipping {key}")
        return False

    try:
        response = requests.post(
            supabase_url().rstrip("/") + "/rest/v1/greg_state",
            headers={
                "apikey": supabase_key(),
                "Authorization": f"Bearer {supabase_key()}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates",
            },
            params={"on_conflict": "key"},
            json={"key": key, "value": value},
            timeout=30,
        )
        if response.status_code in {200, 201, 409}:
            return True
        if verbose:
            print(f"[soul_persist] Upsert {key} failed at tick={tick}: HTTP {response.status_code} {response.text[:200]}")
        return False
    except Exception as exc:
        if verbose:
            print(f"[soul_persist] Upsert {key} error at tick={tick}: {exc}")
        return False


def persist_soul(
    tick: int = 0,
    force: bool = False,
    verbose: bool = True,
    world_path: Path | None = None,
    living_path: Path | None = None,
) -> dict[str, Any]:
    global _last_persist_time

    world_target = Path(world_path or WORLD_STATE_PATH)
    living_target = Path(living_path or LIVING_STATE_PATH)
    result: dict[str, Any] = {
        "ok": False,
        "world_persisted": False,
        "living_persisted": False,
        "tick": tick,
        "world_kb": 0.0,
        "living_kb": 0.0,
        "elapsed_ms": 0.0,
        "supabase_configured": supabase_configured(),
        "world_path": str(world_target),
        "living_path": str(living_target),
    }

    if not force:
        if tick % PERSIST_EVERY != 0:
            result["reason"] = "tick_interval"
            return result
        now = time.time()
        if now - _last_persist_time < MIN_PERSIST_INTERVAL:
            result["reason"] = "rate_limited"
            if verbose:
                print(
                    f"[soul_persist] tick={tick} skipped "
                    f"({int(now - _last_persist_time)}s since last persist)"
                )
            return result

    started = time.time()

    if world_target.exists():
        try:
            payload = _compress_file(world_target)
            result["world_kb"] = round(len(payload) / 1024, 1)
            result["world_persisted"] = _upsert("world_state_gz", payload, tick=tick, verbose=verbose)
        except Exception as exc:
            if verbose:
                print(f"[soul_persist] World persist failed: {exc}")
    else:
        if verbose:
            print(f"[soul_persist] WARNING: world_state.json not found at {world_target}")

    if living_target.exists():
        try:
            payload = _compress_living_state(living_target)
            result["living_kb"] = round(len(payload) / 1024, 1)
            result["living_persisted"] = _upsert("living_state_gz", payload, tick=tick, verbose=verbose)
        except Exception as exc:
            if verbose:
                print(f"[soul_persist] Living state persist failed: {exc}")
    else:
        if verbose:
            print(f"[soul_persist] WARNING: greg_living_state.json not found at {living_target}")

    result["elapsed_ms"] = round((time.time() - started) * 1000, 1)
    result["ok"] = result["world_persisted"] or result["living_persisted"]
    _last_persist_time = time.time()

    try:
        soul_meta = SoulPersist()
        soul_meta.load()
        soul_meta.set("last_persist", result)
    except Exception:
        pass

    if verbose:
        print(
            f"[soul_persist] tick={tick} done in {result['elapsed_ms']}ms | "
            f"world={'yes' if result['world_persisted'] else 'no'} "
            f"living={'yes' if result['living_persisted'] else 'no'}"
        )

    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Persist Greg's soul to Supabase")
    parser.add_argument("--tick", type=int, default=0, help="Current tick number")
    parser.add_argument("--dry-run", action="store_true", help="Compress but do not upload")
    args = parser.parse_args()

    if args.dry_run:
        for label, path, compress_fn in (
            ("world_state", WORLD_STATE_PATH, _compress_file),
            ("living_state", LIVING_STATE_PATH, _compress_living_state),
        ):
            if path.exists():
                source_kb = path.stat().st_size / 1024
                payload = compress_fn(path)
                target_kb = len(payload) / 1024
                reduction = 0 if source_kb == 0 else int((1 - target_kb / source_kb) * 100)
                print(f"{label}: {source_kb:.0f}KB -> {target_kb:.0f}KB ({reduction}% reduction)")
            else:
                print(f"{label}: not found at {path}")
    else:
        print(json.dumps(persist_soul(tick=args.tick, force=True, verbose=True), indent=2))
