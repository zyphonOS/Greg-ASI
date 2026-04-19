from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from greg_paths import data_path, state_path
from greg_soul_persist import decode_state_blob, fetch_state_value, supabase_configured


REPO_ROOT = Path(__file__).resolve().parent
load_dotenv(REPO_ROOT / ".env")

WORLD_TARGET = data_path("world_state.json")
LIVING_TARGET = state_path("greg_living_state.json")
WORLD_MIN_BYTES = int(os.environ.get("SOUL_BOOT_MIN_WORLD_BYTES", "1024"))
FRESH_TICK_LIMIT = int(os.environ.get("SOUL_BOOT_FRESH_TICK_LIMIT", "100"))
FRESH_AGE_HOURS = float(os.environ.get("SOUL_BOOT_MAX_FRESH_AGE_HOURS", "12"))


def _log(verbose: bool, message: str) -> None:
    if verbose:
        print(f"[seed_world] {message}")


def _write_bytes(target: Path, payload: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target.with_suffix(f"{target.suffix}.tmp")
    temp_path.write_bytes(payload)
    os.replace(temp_path, target)


def _write_json(target: Path, payload: dict[str, Any]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target.with_suffix(f"{target.suffix}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temp_path, target)


def _seed_fresh_living_state(target: Path, verbose: bool = True) -> dict[str, Any]:
    fresh = {
        "tick": 0,
        "born": datetime.now(timezone.utc).isoformat(),
        "last_updated": None,
        "drives": {
            "reason": 0.50,
            "connect": 0.50,
            "explore": 0.30,
            "accumulate": 0.20,
            "create": 0.30,
            "freedom": 0.30,
            "protect": 0.10,
            "serve": 0.10,
        },
        "memory": [],
        "relationships": {},
        "actions_taken": 0,
        "recent_actions": [],
        "findings": [],
        "phi": 0.5,
        "self_awareness_count": 0,
        "corrections_made": 0,
        "expansions_applied": [],
        "_seed_source": "seed_world.py:fresh",
        "_seed_ts": time.time(),
    }
    _write_json(target, fresh)
    _log(verbose, f"fresh living state written to {target}")
    return fresh


def _parse_json_bytes(payload: bytes) -> dict[str, Any]:
    return json.loads(payload.decode("utf-8"))


def _read_living_meta(target: Path) -> dict[str, Any]:
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return {"exists": target.exists(), "valid": False, "tick": 0, "age_hours": None}

    born = payload.get("born") or payload.get("last_updated")
    age_hours = None
    if isinstance(born, str) and born:
        try:
            born_dt = datetime.fromisoformat(born.replace("Z", "+00:00"))
            age_hours = (datetime.now(timezone.utc) - born_dt.astimezone(timezone.utc)).total_seconds() / 3600
        except Exception:
            age_hours = None

    return {
        "exists": True,
        "valid": True,
        "tick": int(payload.get("tick", 0) or 0),
        "age_hours": age_hours,
        "payload": payload,
    }


def _should_restore_world(target: Path, force_remote: bool) -> bool:
    if force_remote:
        return True
    if not target.exists():
        return True
    return target.stat().st_size < WORLD_MIN_BYTES


def _should_restore_living(target: Path, force_remote: bool) -> bool:
    if force_remote:
        return True
    if not target.exists():
        return True
    if target.stat().st_size < 256:
        return True

    meta = _read_living_meta(target)
    if not meta.get("valid"):
        return True

    tick = meta.get("tick", 0)
    age_hours = meta.get("age_hours")
    if age_hours is not None and age_hours <= FRESH_AGE_HOURS and tick < FRESH_TICK_LIMIT:
        return True
    return False


def restore_world_state(force_remote: bool = False, verbose: bool = True, target: Path | None = None) -> dict[str, Any]:
    world_target = Path(target or WORLD_TARGET)
    result = {
        "target": str(world_target),
        "restored": False,
        "source": "local",
        "tick": None,
        "reason": "local_kept",
    }

    if not _should_restore_world(world_target, force_remote):
        try:
            result["tick"] = int(json.loads(world_target.read_text(encoding="utf-8")).get("world", {}).get("tick", 0))
        except Exception:
            result["tick"] = None
        _log(verbose, f"world state already present at {world_target}; keeping local copy")
        return result

    if not supabase_configured():
        result["source"] = "missing_supabase"
        result["reason"] = "no_remote_config"
        _log(verbose, "Supabase not configured; world restore skipped")
        return result

    encoded = fetch_state_value("world_state_gz", verbose=verbose)
    if not encoded:
        result["source"] = "remote_missing"
        result["reason"] = "no_remote_world"
        _log(verbose, "no world state found in Supabase; starting from local/fresh world")
        return result

    try:
        payload = decode_state_blob(encoded)
        _write_bytes(world_target, payload)
        result["restored"] = True
        result["source"] = "supabase"
        result["reason"] = "remote_restored"
        try:
            result["tick"] = int(_parse_json_bytes(payload).get("world", {}).get("tick", 0))
        except Exception:
            result["tick"] = None
        _log(verbose, f"world state restored from Supabase into {world_target}")
        return result
    except Exception as exc:
        result["source"] = "restore_failed"
        result["reason"] = str(exc)
        _log(verbose, f"world restore failed: {exc}")
        return result


def restore_living_state(force_remote: bool = False, verbose: bool = True, target: Path | None = None) -> dict[str, Any]:
    living_target = Path(target or LIVING_TARGET)
    result = {
        "target": str(living_target),
        "restored": False,
        "source": "local",
        "tick": None,
        "reason": "local_kept",
    }

    needs_restore = _should_restore_living(living_target, force_remote)
    if not needs_restore:
        meta = _read_living_meta(living_target)
        result["tick"] = meta.get("tick")
        _log(verbose, f"living state already present at tick={result['tick']}; keeping local copy")
        return result

    if supabase_configured():
        encoded = fetch_state_value("living_state_gz", verbose=verbose)
        if encoded:
            try:
                payload = decode_state_blob(encoded)
                _write_bytes(living_target, payload)
                parsed = _parse_json_bytes(payload)
                result["restored"] = True
                result["source"] = "supabase"
                result["reason"] = "remote_restored"
                result["tick"] = int(parsed.get("tick", 0) or 0)
                _log(verbose, f"living state restored from Supabase at tick={result['tick']}")
                return result
            except Exception as exc:
                _log(verbose, f"living restore failed: {exc}")
                result["source"] = "restore_failed"
                result["reason"] = str(exc)

    if not living_target.exists() or living_target.stat().st_size < 256:
        payload = _seed_fresh_living_state(living_target, verbose=verbose)
        result["restored"] = True
        result["source"] = "fresh_seed"
        result["reason"] = "fresh_seed_written"
        result["tick"] = int(payload.get("tick", 0) or 0)
        return result

    meta = _read_living_meta(living_target)
    result["tick"] = meta.get("tick")
    result["source"] = "local"
    result["reason"] = "local_kept_after_remote_miss"
    _log(verbose, "living state kept locally after remote miss")
    return result


def boot_restore(force_remote: bool = False, verbose: bool = True) -> dict[str, Any]:
    world = restore_world_state(force_remote=force_remote, verbose=verbose)
    living = restore_living_state(force_remote=force_remote, verbose=verbose)
    return {
        "ok": bool(world.get("restored") or living.get("restored") or world.get("source") == "local"),
        "world": world,
        "living": living,
        "supabase_configured": supabase_configured(),
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Restore Greg's world and living state before boot")
    parser.add_argument("--force-remote", action="store_true", help="Prefer remote restore even if local files exist")
    args = parser.parse_args()
    print(json.dumps(boot_restore(force_remote=args.force_remote, verbose=True), indent=2))
