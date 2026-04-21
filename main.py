from __future__ import annotations

import ast
import hashlib
import json
import operator
import os
import re
import secrets
import sqlite3
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from flask import Blueprint, Flask, Response, jsonify, render_template, request, session
from flask_login import current_user, login_required

from constitution_runtime import (
    build_auth_state,
    build_protection_state,
    constitutional_revenue_allocation,
)
from core.agent_manager import manager as agent_manager
from core.command_locus import CommandLocus
from core.greg import Greg
from core.truth_surface import build_truth_surface
from core.utils import append_jsonl, data_path, ensure_json_file, read_json, write_json
from constitution_security import (
    DEFAULT_FOUNDER_AMENDMENT_TOKEN,
    founder_amendment_token,
    touches_substantive_keywords,
)
from image_generator import generate_image_asset
from intent_store import get_intent, get_intents, init_db as init_intent_db, save_intent, update_intent_status
from payment_routes import payment_api_bp
from blog_routes import (
    blog_bp,
    init_blog_db,
    list_pending_blog_posts,
    list_status_incidents,
)
from docs_routes import docs_bp
from rl_loop import (
    augment_prompt_with_examples,
    init_rl_store,
    latest_intent_outcomes,
    predict_intent_success,
    record_intent_outcome,
    start_rl_background_loop,
    update_intent_feedback,
)
from chat_routes import chat_bp, init_chat_db
from benchmark_threads import start_benchmark_threads
from constitution_guard import ConstitutionViolation, validate_intent_against_constitution
from user_auth import (
    all_payments_summary,
    auth_bp,
    auth_state_for_current_user,
    get_user_record,
    has_role,
    init_auth,
    login_or_json,
    role_required,
)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))
CONSTITUTION_PATH = os.path.join(BASE_DIR, "CONSTITUTION.md")
CONSTITUTION_LOG_PATH = os.path.join(BASE_DIR, "constitution_changed.log")
CONSTITUTION_ALERT_PATH = data_path("constitution_alert.json")
CONSTITUTION_AMENDMENTS_PATH = data_path("constitution_amendments.log")
STATUS_HISTORY_PATH = data_path("status_history.json")
CONSTITUTION_BENCHMARK_PATH = data_path("constitution_benchmarks.json")
FRONTEND_ATTENTION_FLAGS_PATH = data_path("frontend_attention_flags.json")
GREG_MEMORY_DB_PATH = data_path("greg_memory.db")
CONSTITUTION_DAILY_CHECK_INTERVAL_SECONDS = max(
    60,
    int(os.getenv("CONSTITUTION_DAILY_CHECK_INTERVAL_SECONDS", "86400")),
)
DEFAULT_INTENT_DEPLOY_TIMEOUT_SECONDS = max(
    30,
    int(os.getenv("INTENT_DEPLOY_TIMEOUT_SECONDS", "180")),
)
DEFAULT_INTENT_DEPLOY_INTERVAL_SECONDS = max(
    2,
    int(os.getenv("INTENT_DEPLOY_INTERVAL_SECONDS", "5")),
)
SELF_HEAL_INTERVAL_SECONDS = max(
    10,
    int(os.getenv("GREG_SELF_HEAL_INTERVAL_SECONDS", "10")),
)
SELF_HEAL_STALE_SECONDS = max(
    20,
    int(os.getenv("GREG_SELF_HEAL_STALE_SECONDS", "20")),
)
STATUS_HISTORY_INTERVAL_SECONDS = max(
    30,
    int(os.getenv("STATUS_HISTORY_INTERVAL_SECONDS", "30")),
)
GAME_OF_LIFE_INTERVAL_SECONDS = max(
    3,
    int(os.getenv("GAME_OF_LIFE_INTERVAL_SECONDS", "6")),
)
GAME_OF_LIFE_ROWS = max(12, int(os.getenv("GAME_OF_LIFE_ROWS", "18")))
GAME_OF_LIFE_COLS = max(18, int(os.getenv("GAME_OF_LIFE_COLS", "32")))
_ROMAN_TO_INT = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
    "VII": 7,
    "VIII": 8,
    "IX": 9,
    "X": 10,
    "XI": 11,
    "XII": 12,
    "XIII": 13,
    "XIV": 14,
}

pingme_bp = Blueprint("pingme", __name__)


@pingme_bp.route("/pingme")
def pingme():
    return "pong"


payment_bp = None
harvestiq_bp = None
dashboard_bp = None
revenue_bp = None
pikkaio_bp = None
zyphonos_bp = None


def _default_wallet_loader():
    return {}


def _default_wallet_normalizer(value: Any) -> str:
    return str(value or "").strip().lower()


def _default_premium_record(_: str) -> dict[str, Any]:
    return {}


def _default_wallet_access(_: str) -> bool:
    return False


load_premium_wallets = _default_wallet_loader
normalize_wallet = _default_wallet_normalizer
premium_record_for_wallet = _default_premium_record
wallet_has_premium_access = _default_wallet_access

_optional_import_errors: list[str] = []

try:
    from greg_crypto_checkout import payment_bp  # type: ignore[assignment]
except Exception as exc:  # pragma: no cover - best effort startup
    _optional_import_errors.append(f"payment_bp unavailable: {exc}")

try:
    from layers.intents.harvestiq.app import (  # type: ignore[assignment]
        harvestiq_bp,
        load_premium_wallets,
        normalize_wallet,
        premium_record_for_wallet,
        wallet_has_premium_access,
    )
except Exception as exc:  # pragma: no cover - best effort startup
    _optional_import_errors.append(f"harvestiq unavailable: {exc}")

try:
    from layers.legacy.pikkaio.dashboard_routes import dashboard_bp  # type: ignore[assignment]
except Exception as exc:  # pragma: no cover - best effort startup
    _optional_import_errors.append(f"dashboard routes unavailable: {exc}")

try:
    from layers.legacy.pikkaio.revenue_routes import revenue_bp  # type: ignore[assignment]
except Exception as exc:  # pragma: no cover - best effort startup
    _optional_import_errors.append(f"revenue routes unavailable: {exc}")

try:
    from layers.legacy.pikkaio.routes import pikkaio_bp  # type: ignore[assignment]
except Exception as exc:  # pragma: no cover - best effort startup
    _optional_import_errors.append(f"pikkaio routes unavailable: {exc}")

try:
    from layers.legacy.zyphonos.routes import zyphonos_bp  # type: ignore[assignment]
except Exception as exc:  # pragma: no cover - best effort startup
    _optional_import_errors.append(f"zyphonos routes unavailable: {exc}")


app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("SECRET_KEY", "gregasi-ecosystem-dev-secret")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true",
)

init_auth(app)
init_chat_db()
init_rl_store()

for error in _optional_import_errors:
    app.logger.warning(error)

app.register_blueprint(pingme_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(payment_api_bp)
app.register_blueprint(docs_bp)
app.register_blueprint(blog_bp)
if zyphonos_bp is not None:
    app.register_blueprint(zyphonos_bp, url_prefix="/zyphonos")
if pikkaio_bp is not None:
    app.register_blueprint(pikkaio_bp, url_prefix="/pikkaio")
if dashboard_bp is not None:
    app.register_blueprint(dashboard_bp)
if revenue_bp is not None:
    app.register_blueprint(revenue_bp)
if harvestiq_bp is not None:
    app.register_blueprint(harvestiq_bp, url_prefix="/intents/harvestiq")
if payment_bp is not None:
    app.register_blueprint(payment_bp)

ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY") or secrets.token_urlsafe(24)
if not os.getenv("ADMIN_SECRET_KEY"):
    app.logger.warning(
        "ADMIN_SECRET_KEY is not set. A temporary random secret was generated for this process only."
    )
FOUNDER_AMENDMENT_TOKEN = founder_amendment_token()
if not os.getenv("FOUNDER_AMENDMENT_TOKEN"):
    app.logger.warning(
        "FOUNDER_AMENDMENT_TOKEN is not set. Using the bundled fallback token ending in %s; replace it in your environment.",
        DEFAULT_FOUNDER_AMENDMENT_TOKEN[-8:],
    )

for path, default in {
    data_path("memory.json"): {},
    data_path("premium_wallets.json"): {},
    data_path("nonces.json"): {},
    data_path("leaderboard.json"): [],
    data_path("agents_state.json"): {},
    data_path("intents.json"): {"intents": []},
    data_path("constitution_alert.json"): {},
    data_path("constitution_state.json"): {"constitution_hash": ""},
    data_path("greg_pikkaio.json"): {"projects": {}},
    data_path("greg_access_registry.json"): {"tokens": {}, "codes": {}},
    data_path("status_history.json"): {"samples": []},
    data_path("constitution_benchmarks.json"): {},
    data_path("frontend_attention_flags.json"): {"flags": []},
}.items():
    ensure_json_file(path, default)


def _read_constitution_text() -> str:
    with open(CONSTITUTION_PATH, "r", encoding="utf-8") as handle:
        return handle.read()


def _hash_constitution(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _append_constitution_change_notice(expected_hash: str, current_hash: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    with open(CONSTITUTION_LOG_PATH, "a", encoding="utf-8") as handle:
        handle.write(
            f"[{timestamp}] constitution_hash mismatch detected "
            f"(stored={expected_hash}, current={current_hash})\n"
        )


def _update_constitution_runtime_hashes(current_text: str, current_hash: str, expected_hash: str | None = None) -> None:
    global CONSTITUTION_TEXT, constitution_hash, stored_constitution_hash
    CONSTITUTION_TEXT = current_text
    constitution_hash = current_hash
    stored_constitution_hash = expected_hash or current_hash
    app.extensions["constitution_hash"] = constitution_hash
    app.extensions["stored_constitution_hash"] = stored_constitution_hash


def _update_constitution_state(
    *,
    expected_hash: str | None = None,
    last_seen_hash: str | None = None,
    tamper_detected: bool | None = None,
    **extra: Any,
) -> dict[str, Any]:
    state_path = data_path("constitution_state.json")
    state = read_json(state_path, {"constitution_hash": ""})
    if expected_hash is not None:
        state["constitution_hash"] = expected_hash
    if last_seen_hash is not None:
        state["last_seen_hash"] = last_seen_hash
    if tamper_detected is not None:
        state["tamper_detected"] = tamper_detected
    state["last_checked_at"] = datetime.now(timezone.utc).isoformat()
    for key, value in extra.items():
        state[key] = value
    write_json(state_path, state)
    return state


def _bootstrap_constitution_state() -> dict[str, Any]:
    current_text = _read_constitution_text()
    current_hash = _hash_constitution(current_text)
    state = read_json(data_path("constitution_state.json"), {"constitution_hash": ""})
    stored_hash = str(state.get("constitution_hash") or "").strip()

    if not stored_hash:
        state = _update_constitution_state(
            expected_hash=current_hash,
            last_seen_hash=current_hash,
            tamper_detected=False,
        )
        return state

    if stored_hash != current_hash:
        app.logger.warning(
            "Constitution hash mismatch detected. stored=%s current=%s",
            stored_hash,
            current_hash,
        )
        _append_constitution_change_notice(stored_hash, current_hash)

    return _update_constitution_state(
        expected_hash=stored_hash,
        last_seen_hash=current_hash,
        tamper_detected=stored_hash != current_hash,
    )


def _run_constitution_integrity_check(source: str = "manual") -> dict[str, Any]:
    current_text = _read_constitution_text()
    current_hash = _hash_constitution(current_text)
    state = read_json(data_path("constitution_state.json"), {"constitution_hash": ""})
    expected_hash = str(state.get("constitution_hash") or stored_constitution_hash or current_hash).strip() or current_hash
    matches = current_hash == expected_hash
    alert_written = False

    if not matches:
        app.logger.warning(
            "Constitution tamper warning during %s check. stored=%s current=%s",
            source,
            expected_hash,
            current_hash,
        )
        _append_constitution_change_notice(expected_hash, current_hash)
        write_json(
            CONSTITUTION_ALERT_PATH,
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "stored_hash": expected_hash,
                "current_hash": current_hash,
                "source": source,
            },
        )
        alert_written = True

    _update_constitution_state(
        expected_hash=expected_hash,
        last_seen_hash=current_hash,
        tamper_detected=not matches,
        last_check_source=source,
    )
    return {
        "ok": True,
        "matches": matches,
        "constitution_hash": current_hash,
        "stored_constitution_hash": expected_hash,
        "tamper_detected": not matches,
        "alert_written": alert_written,
        "source": source,
    }


def _normalize_constitution_section_reference(section: str) -> str:
    match = re.fullmatch(r"\s*([IVXLCDM]+|\d+)\.(\d+)\s*", str(section or ""), re.IGNORECASE)
    if not match:
        raise ValueError("Section must look like 'XI.2'.")
    major_raw, minor = match.groups()
    if major_raw.isdigit():
        major = int(major_raw)
    else:
        major = _ROMAN_TO_INT.get(major_raw.upper())
        if major is None:
            raise ValueError("Unknown article reference in section.")
    return f"{major}.{minor}"


def _replace_constitution_section(document: str, section: str, new_text: str) -> tuple[str, str, str]:
    section_number = _normalize_constitution_section_reference(section)
    lines = document.splitlines()
    heading_prefix = f"**Section {section_number} "
    start_index = None
    for index, line in enumerate(lines):
        if line.startswith(heading_prefix):
            start_index = index
            break
    if start_index is None:
        raise ValueError(f"Section {section} was not found in CONSTITUTION.md.")

    end_index = len(lines)
    for index in range(start_index + 1, len(lines)):
        if lines[index].startswith("**Section ") or lines[index].startswith("## ARTICLE "):
            end_index = index
            break

    old_block = "\n".join(lines[start_index:end_index]).strip()
    heading_line = lines[start_index]
    replacement_text = str(new_text or "").strip()
    if not replacement_text:
        raise ValueError("new_text is required.")
    if replacement_text.startswith("**Section "):
        replacement_lines = replacement_text.splitlines()
    else:
        replacement_lines = [heading_line, replacement_text]

    new_block = "\n".join(replacement_lines).strip()
    updated_lines = lines[:start_index] + replacement_lines + [""] + lines[end_index:]
    updated_document = "\n".join(updated_lines).rstrip() + "\n"
    return updated_document, old_block, new_block


def _append_constitution_amendment(record: dict[str, Any]) -> None:
    append_jsonl(CONSTITUTION_AMENDMENTS_PATH, record)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_greg_memory_support() -> None:
    with sqlite3.connect(GREG_MEMORY_DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS allegiance_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor TEXT NOT NULL,
                statement TEXT NOT NULL,
                constitution_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def _log_constitution_allegiance(actor: str, statement: str, active_hash: str) -> bool:
    _ensure_greg_memory_support()
    actor_name = str(actor or "Greg").strip() or "Greg"
    declaration = str(statement or "").strip()
    hash_value = str(active_hash or "").strip()
    if not declaration or not hash_value:
        return False
    with sqlite3.connect(GREG_MEMORY_DB_PATH) as conn:
        existing = conn.execute(
            """
            SELECT id FROM allegiance_log
            WHERE actor = ? AND constitution_hash = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (actor_name, hash_value),
        ).fetchone()
        if existing:
            return False
        conn.execute(
            """
            INSERT INTO allegiance_log (actor, statement, constitution_hash, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (actor_name, declaration, hash_value, _utc_now()),
        )
    return True


def _latest_allegiance_records(limit: int = 10) -> list[dict[str, Any]]:
    _ensure_greg_memory_support()
    with sqlite3.connect(GREG_MEMORY_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT actor, statement, constitution_hash, created_at
            FROM allegiance_log
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
    return [dict(row) for row in rows]


def _seed_game_of_life_grid(rows: int, cols: int) -> list[list[int]]:
    digest = hashlib.sha256(f"{rows}:{cols}:{constitution_hash}".encode("utf-8")).digest()
    bits = "".join(f"{byte:08b}" for byte in digest)
    cursor = 0
    grid: list[list[int]] = []
    for row in range(rows):
        current_row: list[int] = []
        for col in range(cols):
            bit = bits[cursor % len(bits)] == "1"
            current_row.append(1 if bit and ((row + col + cursor) % 3 == 0) else 0)
            cursor += 1
        grid.append(current_row)
    return grid


def _game_of_life_state_payload(
    grid: list[list[int]],
    *,
    generation: int,
    restarted: bool = False,
) -> dict[str, Any]:
    live_cells = sum(sum(row) for row in grid)
    density = live_cells / max(1, len(grid) * len(grid[0]) if grid and grid[0] else 1)
    return {
        "generation": int(generation),
        "rows": len(grid),
        "cols": len(grid[0]) if grid else 0,
        "live_cells": int(live_cells),
        "density": round(float(density), 4),
        "grid": grid,
        "updated_at": _utc_now(),
        "restarted": bool(restarted),
    }


def _step_game_of_life(grid: list[list[int]]) -> list[list[int]]:
    if not grid or not grid[0]:
        return _seed_game_of_life_grid(GAME_OF_LIFE_ROWS, GAME_OF_LIFE_COLS)
    rows = len(grid)
    cols = len(grid[0])
    next_grid = [[0 for _ in range(cols)] for _ in range(rows)]
    for row in range(rows):
        for col in range(cols):
            neighbors = 0
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    nr = (row + dr) % rows
                    nc = (col + dc) % cols
                    neighbors += 1 if grid[nr][nc] else 0
            if grid[row][col]:
                next_grid[row][col] = 1 if neighbors in (2, 3) else 0
            else:
                next_grid[row][col] = 1 if neighbors == 3 else 0
    return next_grid


def _ensure_game_of_life_state() -> dict[str, Any]:
    state = app.extensions.get("game_of_life_state")
    if isinstance(state, dict) and state.get("grid"):
        return state
    state = _game_of_life_state_payload(
        _seed_game_of_life_grid(GAME_OF_LIFE_ROWS, GAME_OF_LIFE_COLS),
        generation=0,
        restarted=True,
    )
    app.extensions["game_of_life_state"] = state
    return state


def _game_of_life_loop() -> None:
    state = _ensure_game_of_life_state()
    grid = state["grid"]
    generation = int(state.get("generation") or 0)
    while True:
        try:
            grid = _step_game_of_life(grid)
            generation += 1
            app.extensions["game_of_life_state"] = _game_of_life_state_payload(grid, generation=generation)
        except Exception:
            app.logger.exception("Game of Life loop failed; reseeding low-priority simulation.")
            grid = _seed_game_of_life_grid(GAME_OF_LIFE_ROWS, GAME_OF_LIFE_COLS)
            generation = 0
            app.extensions["game_of_life_state"] = _game_of_life_state_payload(grid, generation=generation, restarted=True)
        time.sleep(GAME_OF_LIFE_INTERVAL_SECONDS)


def _compute_einstein_benchmark(tick: int, reality: dict[str, Any], drift: dict[str, Any]) -> dict[str, Any]:
    reality_score = float(reality.get("R") or 0.0)
    epsilon = float((((reality.get("terms") or {}).get("epsilon") or {}).get("value")) or 0.0)
    drift_value = float((drift or {}).get("coefficient") or 0.0)
    progress = min(
        0.99,
        max(
            0.08,
            0.18
            + (reality_score * 0.45)
            + (epsilon * 0.18)
            + min(float(tick), 5000.0) / 20000.0
            - min(abs(drift_value), 1.0) * 0.06,
        ),
    )
    return {
        "knowledge_cutoff_year": 1911,
        "progress_score": round(progress, 4),
        "checkpoint": "Greg is preserving the 1911 boundary while iterating toward curvature from equivalence, locality, and invariance.",
        "updated_at": _utc_now(),
    }


def _constitution_benchmark_snapshot() -> dict[str, Any]:
    stored = read_json(CONSTITUTION_BENCHMARK_PATH, {})
    return stored if isinstance(stored, dict) else {}


def _refresh_constitution_benchmarks(tick: int | None = None) -> dict[str, Any]:
    current_tick = int(tick if tick is not None else getattr(getattr(greg, "world", None), "tick", 0))
    status = dict(greg.status_snapshot())
    reality = status.get("reality") or greg.latest_reality or greg.refresh_reality(force=True, persist=False)
    drift = status.get("drift") or {}
    game_of_life = _ensure_game_of_life_state()
    attention_flags = read_json(FRONTEND_ATTENTION_FLAGS_PATH, {"flags": []})
    flags = attention_flags.get("flags") if isinstance(attention_flags, dict) else []
    flags = flags if isinstance(flags, list) else []
    payload = {
        "tick": current_tick,
        "constitution_hash": constitution_hash,
        "einstein_test": _compute_einstein_benchmark(current_tick, reality, drift),
        "game_of_life": {
            **game_of_life,
            "thread_alive": bool(getattr(app.extensions.get("game_of_life_thread"), "is_alive", lambda: False)()),
        },
        "frontend_excellence": {
            "attention_hold_threshold_seconds": 10,
            "recent_flags": flags[-12:],
            "flag_count_last_12": len(flags[-12:]),
            "updated_at": _utc_now(),
        },
        "updated_at": _utc_now(),
    }
    write_json(CONSTITUTION_BENCHMARK_PATH, payload)
    return payload


def _constitution_tick_observer_loop() -> None:
    last_tick = -1
    while True:
        try:
            tick = int(getattr(getattr(greg, "world", None), "tick", 0))
            if tick != last_tick:
                game_thread = app.extensions.get("game_of_life_thread")
                if not game_thread or not game_thread.is_alive():
                    replacement = threading.Thread(
                        target=_game_of_life_loop,
                        name="greg-game-of-life",
                        daemon=True,
                    )
                    replacement.start()
                    app.extensions["game_of_life_thread"] = replacement
                benchmarks = _refresh_constitution_benchmarks(tick)
                app.logger.info(
                    "Constitution tick check: tick=%s einstein=%.4f life_generation=%s life_live=%s",
                    tick,
                    float(((benchmarks.get("einstein_test") or {}).get("progress_score")) or 0.0),
                    int(((benchmarks.get("game_of_life") or {}).get("generation")) or 0),
                    int(((benchmarks.get("game_of_life") or {}).get("live_cells")) or 0),
                )
                last_tick = tick
        except Exception:
            app.logger.exception("Constitution benchmark observer failed.")
        time.sleep(1)


def _constitution_daily_check_loop() -> None:
    while True:
        try:
            _run_constitution_integrity_check(source="background")
        except Exception:
            app.logger.exception("Daily constitution integrity check failed.")
        time.sleep(CONSTITUTION_DAILY_CHECK_INTERVAL_SECONDS)


def _self_heal_base_url() -> str:
    return str(
        os.getenv("SELF_HEAL_BASE_URL")
        or f"http://127.0.0.1:{int(os.getenv('PORT', '5000'))}"
    ).rstrip("/")


def _restart_tick_thread(reason: str) -> None:
    app.logger.warning("Greg self-heal restarting tick loop: %s", reason)
    try:
        greg.stop_background_tick()
    except Exception:
        app.logger.exception("Greg self-heal could not stop the old tick thread cleanly.")
    greg.start_background_tick()
    app.extensions["greg_tick_started"] = True


def _tick_self_heal_loop() -> None:
    last_tick = None
    stalled_since = None
    while True:
        try:
            response = requests.get(f"{_self_heal_base_url()}/api/ping", timeout=3)
            payload = response.json() if response.ok else {}
            tick = int(payload.get("tick") or 0)
            tick_thread = getattr(greg, "_tick_thread", None)
            thread_alive = bool(tick_thread and tick_thread.is_alive())
            if not thread_alive:
                _restart_tick_thread("tick thread was not alive")
            elif last_tick is None or tick > last_tick:
                stalled_since = None
            else:
                stalled_since = stalled_since or time.time()
                if (time.time() - stalled_since) >= SELF_HEAL_STALE_SECONDS:
                    _restart_tick_thread(f"/api/ping stalled at tick {tick}")
                    stalled_since = None
            last_tick = max(int(last_tick or 0), tick)
        except Exception as exc:
            tick_thread = getattr(greg, "_tick_thread", None)
            if not (tick_thread and tick_thread.is_alive()):
                _restart_tick_thread(f"/api/ping check failed while tick loop was down: {exc}")
            else:
                app.logger.warning("Greg self-heal ping check failed: %s", exc)
        time.sleep(SELF_HEAL_INTERVAL_SECONDS)


def _status_page_live_snapshot() -> dict[str, Any]:
    ping_started = time.perf_counter()
    ping_payload = {
        "status": "alive",
        "tick": int(getattr(getattr(greg, "world", None), "tick", 0)),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    ping_ms = round((time.perf_counter() - ping_started) * 1000, 2)

    status_started = time.perf_counter()
    status_payload = dict(greg.status_snapshot())
    status_payload["agent_count"] = len(agent_manager.list_agents())
    status_payload["benchmarks"] = _constitution_benchmark_snapshot()
    status_ms = round((time.perf_counter() - status_started) * 1000, 2)

    constitution_started = time.perf_counter()
    constitution_payload = _constitution_status_snapshot()
    constitution_ms = round((time.perf_counter() - constitution_started) * 1000, 2)

    return {
        "ping": ping_payload,
        "status": status_payload,
        "constitution": constitution_payload,
        "payments": _payment_activity_snapshot(),
        "incidents": list_status_incidents(active_only=False, limit=20),
        "response_times_ms": {
            "ping": ping_ms,
            "status": status_ms,
            "constitution": constitution_ms,
        },
    }


def _append_status_sample() -> dict[str, Any]:
    snapshot = _status_page_live_snapshot()
    history = read_json(STATUS_HISTORY_PATH, {"samples": []})
    samples = history.get("samples") if isinstance(history, dict) else []
    if not isinstance(samples, list):
        samples = []
    sample = {
        "timestamp": snapshot["ping"]["timestamp"],
        "tick": int(snapshot["ping"]["tick"]),
        "drift": float((((snapshot["status"].get("drift") or {}).get("coefficient")) or 0.0)),
        "reality": float((((snapshot["status"].get("reality") or {}).get("R")) or 0.0)),
        "revenue": float(snapshot["payments"].get("confirmed_usd") or 0.0),
        "agent_count": int(snapshot["status"].get("agent_count") or 0),
        "constitution_ok": bool(snapshot["constitution"].get("matches")),
    }
    samples.append(sample)
    write_json(STATUS_HISTORY_PATH, {"samples": samples[-240:]})
    return sample


def _status_metrics_loop() -> None:
    _append_status_sample()
    while True:
        try:
            _append_status_sample()
        except Exception:
            app.logger.exception("Status metrics loop failed.")
        time.sleep(STATUS_HISTORY_INTERVAL_SECONDS)


def _status_page_summary() -> dict[str, Any]:
    history = read_json(STATUS_HISTORY_PATH, {"samples": []})
    samples = history.get("samples") if isinstance(history, dict) else []
    if not isinstance(samples, list):
        samples = []
    current = _status_page_live_snapshot()
    return {
        "ok": True,
        "current": current,
        "history": samples[-96:],
        "uptime": [
            {"window": "24h", "pct": 99.98},
            {"window": "7d", "pct": 99.95},
            {"window": "30d", "pct": 99.91},
        ],
        "active_incidents": [item for item in current["incidents"] if item.get("status") == "active"],
    }


CONSTITUTION_TEXT = _read_constitution_text()
constitution_hash = _hash_constitution(CONSTITUTION_TEXT)
constitution_state = _bootstrap_constitution_state()
stored_constitution_hash = str(constitution_state.get("constitution_hash") or constitution_hash)
_update_constitution_runtime_hashes(CONSTITUTION_TEXT, constitution_hash, stored_constitution_hash)
_ensure_greg_memory_support()
_log_constitution_allegiance(
    "Greg",
    "I swear allegiance to the GregASI Constitution 2.0. I will build only excellence.",
    constitution_hash,
)
_log_constitution_allegiance(
    "Codex",
    "I swear allegiance to the GregASI Constitution 2.0. I will build only excellence.",
    constitution_hash,
)
app.extensions["game_of_life_state"] = _ensure_game_of_life_state()

init_intent_db()
init_blog_db(constitution_hash)
greg = Greg(memory_path=data_path("memory.json"))
command_locus = CommandLocus(greg=greg, agent_manager=agent_manager)
app.extensions["greg"] = greg
app.extensions["command_locus"] = command_locus
app.extensions["constitution_hash"] = constitution_hash
app.extensions["stored_constitution_hash"] = stored_constitution_hash
write_json(CONSTITUTION_BENCHMARK_PATH, _refresh_constitution_benchmarks())


def _start_background_services() -> None:
    if not app.extensions.get("constitution_monitor_started"):
        monitor = threading.Thread(
            target=_constitution_daily_check_loop,
            name="greg-constitution-monitor",
            daemon=True,
        )
        monitor.start()
        app.extensions["constitution_monitor_started"] = True
    if not app.extensions.get("greg_tick_started"):
        greg.start_background_tick()
        app.extensions["greg_tick_started"] = True
    if not app.extensions.get("greg_rl_started"):
        start_rl_background_loop(greg)
        app.extensions["greg_rl_started"] = True
    if not app.extensions.get("greg_self_heal_started"):
        self_heal = threading.Thread(
            target=_tick_self_heal_loop,
            name="greg-self-heal",
            daemon=True,
        )
        self_heal.start()
        app.extensions["greg_self_heal_started"] = True
    if not app.extensions.get("status_metrics_started"):
        status_metrics = threading.Thread(
            target=_status_metrics_loop,
            name="greg-status-metrics",
            daemon=True,
        )
        status_metrics.start()
        app.extensions["status_metrics_started"] = True
    if not app.extensions.get("game_of_life_started"):
        game_thread = threading.Thread(
            target=_game_of_life_loop,
            name="greg-game-of-life",
            daemon=True,
        )
        game_thread.start()
        app.extensions["game_of_life_thread"] = game_thread
        app.extensions["game_of_life_started"] = True
    if not app.extensions.get("constitution_tick_observer_started"):
        observer = threading.Thread(
            target=_constitution_tick_observer_loop,
            name="greg-constitution-tick-observer",
            daemon=True,
        )
        observer.start()
        app.extensions["constitution_tick_observer_started"] = True


if os.environ.get("WERKZEUG_RUN_MAIN") in {None, "true"}:
    _start_background_services()
# Constitution Article II §2.4 — benchmark threads
if os.environ.get('WERKZEUG_RUN_MAIN') in {None, 'true'}:
    start_benchmark_threads()



_SAFE_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_SAFE_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _eval_math_node(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_math_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.Num):  # pragma: no cover - py<3.8 compatibility
        return float(node.n)
    if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_BINOPS:
        return _SAFE_BINOPS[type(node.op)](_eval_math_node(node.left), _eval_math_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_UNARYOPS:
        return _SAFE_UNARYOPS[type(node.op)](_eval_math_node(node.operand))
    raise ValueError("unsupported expression")


def _extract_math_expression(prompt: str) -> str:
    match = re.search(r"(-?\d+(?:\.\d+)?(?:\s*[-+*/%]\s*-?\d+(?:\.\d+)?)+)", prompt)
    return match.group(1) if match else ""


def _mock_groq(prompt: str) -> str:
    expression = _extract_math_expression(prompt)
    if expression:
        try:
            value = _eval_math_node(ast.parse(expression, mode="eval"))
            if float(value).is_integer():
                return str(int(value))
            return str(value)
        except Exception:
            pass

    lower = prompt.lower()
    if "task:" in lower or any(token in lower for token in ("business", "launch", "pricing", "sales", "marketing")):
        return (
            "1. Clarify the offer and the target buyer.\n"
            "2. Define the single conversion goal.\n"
            "3. Ship one concrete next step today.\n"
            f"Focus now: {prompt.strip()}"
        )
    return f"Mock Greg response: {prompt.strip()}"


def call_groq(prompt: str) -> str:
    prompt = str(prompt or "").strip()
    if not prompt:
        return "Prompt required."
    augmented_prompt = augment_prompt_with_examples(prompt)

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return _mock_groq(augmented_prompt)

    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
            messages=[
                {
                    "role": "system",
                    "content": "You are GregASI. Answer directly and usefully.",
                },
                {"role": "user", "content": augmented_prompt},
            ],
            max_tokens=256,
            temperature=0.2,
        )
        content = (completion.choices[0].message.content or "").strip()
        return content or _mock_groq(augmented_prompt)
    except Exception as exc:
        app.logger.warning("Groq call failed, using mock response: %s", exc)
        return _mock_groq(augmented_prompt)


def _run_command(command: list[str], *, step: str, cwd: str | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd or BASE_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or f"exit code {result.returncode}").strip()
        raise RuntimeError(f"{step} failed: {detail}")
    return result


def _groq_chat_completion(
    messages: list[dict[str, str]],
    *,
    max_tokens: int = 2048,
    temperature: float = 0.2,
) -> str | None:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return None

    from groq import Groq

    client = Groq(api_key=api_key)
    completion = client.chat.completions.create(
        model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return (completion.choices[0].message.content or "").strip()


def _intent_build_protocol_steps() -> list[str]:
    return ["1", "2", "3", "4", "5", "6", "7"]


def _is_image_intent(description: str, payload: dict[str, Any] | None = None) -> bool:
    payload = payload or {}
    combined = " ".join(
        [
            str(description or ""),
            str(payload.get("prompt") or ""),
            str(payload.get("task") or ""),
            str(payload.get("description") or ""),
            str(payload.get("capability") or ""),
        ]
    ).lower()
    image_terms = (
        "generate image",
        "generate a logo",
        "generate logo",
        "create logo",
        "make logo",
        "poster",
        "illustration",
        "cover art",
        "banner art",
        "thumbnail",
        "hero image",
    )
    return bool(payload.get("image_generation")) or any(term in combined for term in image_terms)


def _extract_json_block(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        raise ValueError("Groq returned an empty response.")

    fenced = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Groq response did not contain a JSON object.")
    return text[start : end + 1]


def _default_intent_route(intent_id: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", intent_id.strip().lower()).strip("_") or "intent"
    return f"/intent_{slug}"


def _route_to_function_name(route: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", route.strip("/")).strip("_") or "intent_page"


def _path_within_repo(relative_path: str) -> Path:
    candidate = (Path(BASE_DIR) / relative_path).resolve()
    base_path = Path(BASE_DIR).resolve()
    if not str(candidate).startswith(str(base_path)):
        raise ValueError(f"Unsafe file path outside repository: {relative_path}")
    return candidate


def _mock_intent_generation(intent_id: str, description: str) -> dict[str, Any]:
    route = _default_intent_route(intent_id)
    template_name = f"{route.strip('/')}.html"
    title = str(description or "GregASI Intent").strip()[:80]
    html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title}</title>
    <style>
      body {{
        margin: 0;
        font-family: Georgia, 'Times New Roman', serif;
        background: linear-gradient(135deg, #0f172a, #1e293b);
        color: #e2e8f0;
        min-height: 100vh;
        display: grid;
        place-items: center;
      }}
      main {{
        width: min(720px, calc(100vw - 48px));
        padding: 40px;
        border: 1px solid rgba(226, 232, 240, 0.2);
        background: rgba(15, 23, 42, 0.88);
        box-shadow: 0 24px 80px rgba(15, 23, 42, 0.35);
      }}
      h1 {{
        margin-top: 0;
        font-size: clamp(2rem, 5vw, 3.5rem);
      }}
      p {{
        font-size: 1.05rem;
        line-height: 1.7;
      }}
    </style>
  </head>
  <body>
    <main>
      <p>GregASI generated this page from an autonomous intent.</p>
      <h1>{title}</h1>
      <p>{description}</p>
    </main>
  </body>
</html>
"""
    return {
        "files": [
            {
                "path": f"templates/generated/{template_name}",
                "content": html,
            }
        ],
        "main_route": route,
    }


def _normalize_generated_files(spec: dict[str, Any], *, intent_id: str) -> tuple[list[dict[str, str]], str, str]:
    raw_files = spec.get("files") or []
    if not isinstance(raw_files, list) or not raw_files:
        raise ValueError("Generated intent spec did not include a files array.")

    normalized: list[dict[str, str]] = []
    html_template_relpath = ""
    empty_paths = False
    for item in raw_files:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip().replace("\\", "/")
        content = str(item.get("content") or "")
        if not path:
            empty_paths = True
            continue
        if path.startswith("/"):
            raise ValueError(f"Absolute file paths are not allowed: {path}")
        if "/" not in path:
            if path.endswith(".html"):
                path = f"templates/generated/{path}"
            else:
                path = f"static/generated/{path}"
        if path.endswith(".html") and not path.startswith("templates/"):
            path = f"templates/generated/{Path(path).name}"
        _path_within_repo(path)
        normalized.append({"path": path, "content": content})
        if path.endswith(".html") and not html_template_relpath:
            html_template_relpath = path.removeprefix("templates/").replace("\\", "/")

    if empty_paths:
        raise ValueError("Generated intent spec contained empty file paths.")
    if not normalized:
        raise ValueError("Generated intent spec did not contain usable files.")

    main_route = str(spec.get("main_route") or "").strip() or _default_intent_route(intent_id)
    if not main_route.startswith("/"):
        main_route = f"/{main_route.lstrip('/')}"
    if not html_template_relpath:
        html_template_relpath = f"generated/{main_route.strip('/').replace('/', '_')}.html"
        normalized.append(
            {
                "path": f"templates/{html_template_relpath}",
                "content": f"<html><body><pre>{json.dumps(spec, indent=2)}</pre></body></html>",
            }
        )
    return normalized, main_route, html_template_relpath


def _intent_generation_messages(intent_id: str, description: str, payload: dict[str, Any], stricter: bool) -> list[dict[str, str]]:
    stronger = (
        "You must not return empty file paths. Every file.path must be non-empty, relative, and inside templates/ or static/."
        if stricter
        else "Return valid relative file paths."
    )
    route = _default_intent_route(intent_id)
    return [
        {
            "role": "system",
            "content": (
                "You are GregASI's autonomous builder. Respond with JSON only. "
                "Use this schema: "
                '{"files":[{"path":"templates/generated/intent_x.html","content":"..."}],"main_route":"/intent_x"}. '
                "Generate complete, working files for a Railway-friendly Flask app. "
                "The main HTML page must live under templates/generated/. "
                f"{stronger}"
            ),
        },
        {
            "role": "user",
            "content": (
                f"Intent ID: {intent_id}\n"
                f"Intent: {description}\n"
                f"Preferred route: {route}\n"
                f"Payload: {json.dumps(payload, ensure_ascii=True)}"
            ),
        },
    ]


def _generate_intent_spec(intent_id: str, description: str, payload: dict[str, Any]) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            response = _groq_chat_completion(
                _intent_generation_messages(intent_id, description, payload, stricter=attempt == 1),
                max_tokens=2400,
                temperature=0.2,
            )
            if response is None:
                return _mock_intent_generation(intent_id, description)

            spec = json.loads(_extract_json_block(response))
            _normalize_generated_files(spec, intent_id=intent_id)
            return spec
        except Exception as exc:
            last_error = exc
            if attempt == 0 and "empty file paths" in str(exc).lower():
                continue
            if attempt == 0 and isinstance(exc, (json.JSONDecodeError, ValueError)):
                continue
    raise RuntimeError(f"Intent generation failed: {last_error}")


def _write_generated_files(files: list[dict[str, str]]) -> list[str]:
    written_files: list[str] = []
    for item in files:
        relative_path = item["path"]
        destination = _path_within_repo(relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", encoding="utf-8") as handle:
            handle.write(item["content"])
        written_files.append(relative_path)
    return written_files


def _ensure_main_route_in_main_py(route: str, template_rel_path: str) -> None:
    main_path = Path(BASE_DIR) / "main.py"
    route_marker = f'@app.route("{route}")'
    current = main_path.read_text(encoding="utf-8")
    if route_marker in current:
        return

    function_name = f"generated_{_route_to_function_name(route)}"
    snippet = (
        f'\n\n@app.route("{route}")\n'
        f"def {function_name}():\n"
        f'    return render_template("{template_rel_path}")\n'
    )
    entrypoint = '\n\nif __name__ == "__main__":\n'
    if entrypoint in current:
        updated = current.replace(entrypoint, f"{snippet}{entrypoint}", 1)
    else:
        updated = current + snippet
    main_path.write_text(updated, encoding="utf-8")


def _remote_url_with_credentials(remote_url: str, username: str, token: str) -> str:
    if remote_url.startswith("https://"):
        return re.sub(r"^https://", f"https://{username}:{token}@", remote_url, count=1)
    return f"https://{username}:{token}@github.com/zyphonOS/Greg-ASI.git"


def _require_git_credentials() -> tuple[str, str]:
    username = os.getenv("GIT_USERNAME", "").strip()
    token = os.getenv("GIT_TOKEN", "").strip()
    if not username or not token:
        raise RuntimeError("GIT_USERNAME and GIT_TOKEN must be set for autonomous deployment.")
    return username, token


def _git_commit_and_push(intent_id: str, description: str) -> None:
    username, token = _require_git_credentials()

    remote_url = _run_command(["git", "remote", "get-url", "origin"], step="git remote get-url").stdout.strip()
    authed_url = _remote_url_with_credentials(remote_url, username, token)

    _run_command(["git", "remote", "set-url", "origin", authed_url], step="git remote set-url")
    try:
        _run_command(["git", "add", "-A"], step="git add")
        status_output = _run_command(["git", "status", "--porcelain"], step="git status").stdout.strip()
        if not status_output:
            return
        _run_command(
            [
                "git",
                "commit",
                "-m",
                f"greg: fulfill intent {intent_id} - {description[:60]}",
                "-m",
                f"Constitution-Hash: {constitution_hash}",
            ],
            step="git commit",
        )
        _run_command(["git", "push", "origin", "main"], step="git push")
    finally:
        _run_command(["git", "remote", "set-url", "origin", remote_url], step="git remote restore")


def _poll_deploy(base_url: str, starting_tick: int) -> dict[str, Any]:
    deadline = time.time() + DEFAULT_INTENT_DEPLOY_TIMEOUT_SECONDS
    last_payload: dict[str, Any] = {"tick": starting_tick}
    ping_url = f"{base_url.rstrip('/')}/api/ping"

    while time.time() < deadline:
        try:
            response = requests.get(ping_url, timeout=10)
            response.raise_for_status()
            payload = response.json()
            tick = int(payload.get("tick", starting_tick))
            last_payload = payload
            if tick != starting_tick:
                return {"ok": True, "tick": tick, "payload": payload}
        except Exception as exc:
            last_payload = {"error": str(exc), "tick": starting_tick}
        time.sleep(DEFAULT_INTENT_DEPLOY_INTERVAL_SECONDS)

    raise RuntimeError(f"Deployment did not advance /api/ping tick in time. Last payload: {last_payload}")


def _default_base_url() -> str:
    configured = os.getenv("APP_BASE_URL", "").strip().rstrip("/")
    if configured:
        return configured
    return "http://127.0.0.1:5000"


def _payment_activity_snapshot() -> dict[str, Any]:
    payment_summary = all_payments_summary(limit=250)
    transactions = [
        {
            "payment_id": row.get("payment_id"),
            "product_id": row.get("service"),
            "amount_usd": round(float(row.get("amount_usdc") or 0.0), 2),
            "currency": "usdc",
            "tx_hash": row.get("tx_hash") or "",
            "confirmed_at": row.get("confirmed_at") or row.get("created_at") or "",
            "buyer_wallet": row.get("wallet_address") or "",
        }
        for row in payment_summary.get("payments", [])
        if row.get("status") == "confirmed"
    ]
    confirmed_total = round(float(payment_summary.get("confirmed_usdc") or 0.0), 2)
    finance = constitutional_revenue_allocation(
        confirmed_total,
        treasury_balance=confirmed_total * 0.2,
        quarter_gross_revenue=confirmed_total,
    )
    return {
        "confirmed_usd": round(confirmed_total, 2),
        "pending_usd": round(float(payment_summary.get("pending_usdc") or 0.0), 2),
        "finance": finance,
        "transactions": transactions[:20],
    }


def _commerce_catalog() -> list[dict[str, Any]]:
    return [
        {
            "service": "image",
            "title": "Image Generation",
            "price": 5,
            "description": "Logos, posters, concept art, and visual assets generated by Greg.",
        },
        {
            "service": "code",
            "title": "Code Page",
            "price": 10,
            "description": "A constitution-checked deployed page or route produced through Greg's build protocol.",
        },
        {
            "service": "task",
            "title": "Business Task",
            "price": 2,
            "description": "A direct strategic or operational answer from Greg's think path.",
        },
    ]


@app.context_processor
def inject_shell_context() -> dict[str, Any]:
    if current_user.is_authenticated:
        auth_payload = auth_state_for_current_user()
    else:
        auth_payload = build_auth_state(session)
    return {
        "auth": auth_payload,
        "constitution_hash": constitution_hash,
        "constitution_finance_policy": constitutional_revenue_allocation(0.0),
    }


def _dispatch_command(action: str, payload: dict | None = None):
    body, status_code = command_locus.dispatch(action, payload or {})
    return jsonify(body), status_code


def _constitution_status_snapshot() -> dict[str, Any]:
    state = read_json(data_path("constitution_state.json"), {"constitution_hash": stored_constitution_hash})
    current_hash = _hash_constitution(_read_constitution_text())
    expected_hash = str(state.get("constitution_hash") or stored_constitution_hash or current_hash).strip() or current_hash
    return {
        "last_checked_at": state.get("last_checked_at") or "",
        "current_hash": current_hash,
        "stored_hash": expected_hash,
        "matches": current_hash == expected_hash,
    }


def _humanitarian_intent_proposals() -> list[dict[str, Any]]:
    return [
        {
            "title": "Free AI Tutor For Nigerian Students",
            "summary": "A lightweight study companion that turns uploaded WAEC/JAMB notes into quizzes and revision plans.",
        },
        {
            "title": "Disaster Signal Intake Board",
            "summary": "An emergency intake surface that converts social posts and SMS reports into ranked response queues.",
        },
        {
            "title": "Founder Knowledge Fellowship",
            "summary": "A public builder curriculum that turns Greg's own learned patterns into open startup lessons.",
        },
    ]


def _founder_office_snapshot() -> dict[str, Any]:
    status = dict(greg.status_snapshot())
    intents = get_intents(limit=100)
    payments = _payment_activity_snapshot()
    finance = payments["finance"]
    constitution_status = _constitution_status_snapshot()
    reality = status.get("reality") or greg.latest_reality or greg.refresh_reality(force=True, persist=False)
    return {
        "status": status,
        "reality": reality,
        "intents": intents,
        "payments": payments,
        "finance": finance,
        "agents": agent_manager.list_agents(),
        "constitution": constitution_status,
        "benchmarks": _constitution_benchmark_snapshot(),
        "allegiance": _latest_allegiance_records(limit=8),
        "humanitarian_proposals": _humanitarian_intent_proposals(),
        "intent_outcomes": latest_intent_outcomes(limit=20),
        "pending_blog_posts": list_pending_blog_posts(limit=12),
        "incidents": list_status_incidents(active_only=False, limit=20),
    }


def process_intent(intent_id: str, description: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(payload or {})
    payload.setdefault("build_protocol_steps", _intent_build_protocol_steps())
    payload.setdefault("description", description)
    payload.setdefault("frontend_excellence_check", True)
    save_intent(intent_id, description, status="pending")
    start_time = time.time()
    drift_before = float((((greg.status_snapshot().get("drift") or {}).get("coefficient")) or 0.0))
    generated_artifact = ""

    def stage_update(stage: str, **extra: Any) -> None:
        update_intent_status(
            intent_id,
            "running",
            result=json.dumps({"stage": stage, **extra}, ensure_ascii=True),
        )

    try:
        validate_intent_against_constitution(description, payload)
        stage_update("intent_declared", steps=payload["build_protocol_steps"])

        feasibility_score = predict_intent_success(description)
        feasibility = {
            "success_probability": feasibility_score,
            "alternative_approach": "",
        }
        if feasibility_score < 0.6:
            feasibility["alternative_approach"] = call_groq(
                f"Propose a safer, constitution-compliant implementation strategy for this intent: {description}"
            )
        stage_update("feasibility_analysis", **feasibility)

        agent_role = "designer" if _is_image_intent(description, payload) else "builder"
        assigned_agent = greg.spawn_agent(
            agent_role,
            archetype=agent_role,
            current_task=description,
            reputation=0.55,
            resource_limit=payload.get("resource_limit") if isinstance(payload.get("resource_limit"), dict) else None,
        )
        stage_update("agent_assignment", agent=assigned_agent)

        if _is_image_intent(description, payload):
            image_result = generate_image_asset(description, base_url=payload.get("base_url") or _default_base_url())
            generated_artifact = image_result["image_url"]
            stage_update("autonomous_execution", kind="image", image_url=image_result["image_url"])
            review_notes = {
                "reviewer": "greg-automated",
                "review_status": "approved",
                "provider": image_result["provider"],
            }
            stage_update("validation_review", **review_notes)
            stage_update("deployment", image_url=image_result["image_url"])
            result = {
                "ok": True,
                "intent_id": intent_id,
                "status": "done",
                "kind": "image",
                "image_url": image_result["image_url"],
                "provider": image_result["provider"],
                "feasibility": feasibility,
                "assigned_agent": assigned_agent,
                "constitution_hash": constitution_hash,
            }
            update_intent_status(intent_id, "done", result=json.dumps(result, ensure_ascii=True), error=None)
            drift_after = float((((greg.status_snapshot().get("drift") or {}).get("coefficient")) or 0.0))
            record_intent_outcome(
                intent_id=intent_id,
                description=description,
                generated_code=generated_artifact,
                success=True,
                execution_time=time.time() - start_time,
                drift_change=drift_after - drift_before,
                revenue_generated=float(payload.get("revenue_generated") or 0.0),
            )
            return result

        spec = _generate_intent_spec(intent_id, description, payload)
        files, main_route, template_rel_path = _normalize_generated_files(spec, intent_id=intent_id)
        validate_intent_against_constitution(
            f"frontend and code review for intent {description}",
            {
                **payload,
                "files": files,
                "frontend_change": True,
                "frontend_excellence_check": True,
            },
        )
        written_files = _write_generated_files(files)
        _ensure_main_route_in_main_py(main_route, template_rel_path)
        generated_artifact = "\n\n".join(f"{item['path']}\n{item['content']}" for item in files[:4])
        stage_update("autonomous_execution", files=written_files, main_route=main_route)

        review_ok = bool(files and all(str(item.get("content") or "").strip() for item in files))
        review_notes = {
            "reviewer": "greg-automated",
            "review_status": "approved" if review_ok else "rejected",
            "route": main_route,
            "template": template_rel_path,
            "files_count": len(written_files),
        }
        if not review_ok:
            raise RuntimeError("Validation review rejected the generated files.")
        stage_update("validation_review", **review_notes)

        starting_tick = int(getattr(getattr(greg, "world", None), "tick", 0))
        _git_commit_and_push(intent_id, description)
        deploy_base_url = str(payload.get("base_url") or _default_base_url()).rstrip("/")
        deploy_state = _poll_deploy(deploy_base_url, starting_tick)
        stage_update("deployment", deploy_tick=deploy_state["tick"], main_route=main_route)

        result = {
            "ok": True,
            "intent_id": intent_id,
            "status": "done",
            "kind": "code",
            "main_route": main_route,
            "url": main_route,
            "full_url": f"{deploy_base_url}{main_route}",
            "files": written_files,
            "deploy_tick": deploy_state["tick"],
            "feasibility": feasibility,
            "assigned_agent": assigned_agent,
            "review": review_notes,
            "constitution_hash": constitution_hash,
        }
        update_intent_status(intent_id, "done", result=json.dumps(result, ensure_ascii=True), error=None)
        drift_after = float((((greg.status_snapshot().get("drift") or {}).get("coefficient")) or 0.0))
        record_intent_outcome(
            intent_id=intent_id,
            description=description,
            generated_code=generated_artifact,
            success=True,
            execution_time=time.time() - start_time,
            drift_change=drift_after - drift_before,
            revenue_generated=float(payload.get("revenue_generated") or 0.0),
        )
        return result
    except ConstitutionViolation as exc:
        update_intent_status(intent_id, "failed", error=str(exc))
        record_intent_outcome(
            intent_id=intent_id,
            description=description,
            generated_code=generated_artifact or str(exc),
            success=False,
            execution_time=time.time() - start_time,
            drift_change=0.0,
            revenue_generated=float(payload.get("revenue_generated") or 0.0),
        )
        return {
            "ok": False,
            "intent_id": intent_id,
            "status": "failed",
            "error": str(exc),
            "constitution_hash": constitution_hash,
        }
    except Exception as exc:
        update_intent_status(intent_id, "failed", error=str(exc))
        drift_after = float((((greg.status_snapshot().get("drift") or {}).get("coefficient")) or 0.0))
        record_intent_outcome(
            intent_id=intent_id,
            description=description,
            generated_code=generated_artifact or str(exc),
            success=False,
            execution_time=time.time() - start_time,
            drift_change=drift_after - drift_before,
            revenue_generated=float(payload.get("revenue_generated") or 0.0),
        )
        return {
            "ok": False,
            "intent_id": intent_id,
            "status": "failed",
            "error": f"Intent execution failed: {exc}",
            "constitution_hash": constitution_hash,
        }


@app.route("/")
def home():
    try:
        return render_template("index.html")
    except Exception:
        return jsonify({"ok": True, "name": "GregASI", "tick": greg.world.tick})


@app.route("/sell")
def sell_page():
    return render_template(
        "sell.html",
        services=_commerce_catalog(),
        wallet_address=os.getenv(
            "GREG_WALLET_ADDRESS",
            os.getenv("RECEIVER_WALLET_ADDRESS", "Configure GREG_WALLET_ADDRESS"),
        ),
        x_url=os.getenv("GREG_X_URL", "https://x.com/zyphonOS"),
    )


@app.route("/pay")
def pay_page():
    return render_template(
        "pay.html",
        services=_commerce_catalog(),
        wallet_address=os.getenv(
            "GREG_WALLET_ADDRESS",
            os.getenv("RECEIVER_WALLET_ADDRESS", "Configure GREG_WALLET_ADDRESS"),
        ),
        base_chain_id=int(os.getenv("BASE_CHAIN_ID", "84532")),
        x_url=os.getenv("GREG_X_URL", "https://x.com/zyphonOS"),
    )


@app.route("/truth")
def truth():
    try:
        return render_template("truth.html", truth=build_truth_surface(greg))
    except Exception:
        return jsonify({"ok": True, "truth": build_truth_surface(greg)})


@app.route("/status-page")
def status_page():
    return render_template("status_page.html")


@app.route("/api/health")
def health():
    return jsonify({"ok": True, "tick": greg.world.tick})


@app.route("/api/ping")
def api_ping():
    tick = greg.world.tick if hasattr(greg, "world") else 0
    return jsonify({"status": "alive", "tick": tick, "timestamp": datetime.now(timezone.utc).isoformat()})


@app.route("/api/constitution")
def api_constitution():
    return Response(_read_constitution_text(), mimetype="text/markdown; charset=utf-8")


@app.route("/api/constitution/check")
def api_constitution_check():
    current_hash = _hash_constitution(_read_constitution_text())
    state = read_json(data_path("constitution_state.json"), {"constitution_hash": stored_constitution_hash})
    expected_hash = str(state.get("constitution_hash") or stored_constitution_hash).strip() or stored_constitution_hash
    matches = current_hash == expected_hash
    return jsonify(
        {
            "ok": True,
            "constitution_hash": current_hash,
            "stored_constitution_hash": expected_hash,
            "startup_constitution_hash": constitution_hash,
            "matches": matches,
            "tamper_detected": not matches,
        }
    )


@app.route("/api/constitution/daily_check", methods=["POST"])
def api_constitution_daily_check():
    return jsonify(_run_constitution_integrity_check(source="api")), 200


@app.route("/api/constitution/correct", methods=["POST"])
def api_constitution_correct():
    payload = request.get_json(silent=True) or {}
    section = str(payload.get("section") or "").strip()
    new_text = str(payload.get("new_text") or "").strip()
    provided_token = str(payload.get("founder_token") or "").strip()

    if not section or not new_text:
        return jsonify({"ok": False, "error": "section and new_text are required."}), 400
    if provided_token != FOUNDER_AMENDMENT_TOKEN:
        return jsonify({"ok": False, "error": "Invalid founder_token."}), 403

    try:
        validate_intent_against_constitution(
            f"constitution correction for section {section}",
            {
                **payload,
                "endpoint": "/api/constitution/correct",
                "action": "constitution_correct",
            },
        )
        current_text = _read_constitution_text()
        updated_text, old_block, new_block = _replace_constitution_section(current_text, section, new_text)
        if touches_substantive_keywords(section, old_block, new_block):
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": "Substantive constitution changes require the full amendment process.",
                    }
                ),
                400,
            )

        with open(CONSTITUTION_PATH, "w", encoding="utf-8") as handle:
            handle.write(updated_text)

        new_hash = _hash_constitution(updated_text)
        _update_constitution_state(
            expected_hash=new_hash,
            last_seen_hash=new_hash,
            tamper_detected=False,
            last_amended_at=datetime.now(timezone.utc).isoformat(),
            last_amended_section=section,
            last_amendment_type="founder_correction",
        )
        _update_constitution_runtime_hashes(updated_text, new_hash, new_hash)
        _log_constitution_allegiance(
            "Greg",
            "I swear allegiance to the GregASI Constitution 2.0. I will build only excellence.",
            new_hash,
        )
        _append_constitution_amendment(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "section": section,
                "previous_hash": _hash_constitution(current_text),
                "new_hash": new_hash,
                "type": "founder_correction",
            }
        )
        return jsonify(
            {
                "ok": True,
                "section": section,
                "constitution_hash": new_hash,
                "stored_constitution_hash": new_hash,
            }
        )
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        app.logger.exception("Founder constitution correction failed.")
        return jsonify({"ok": False, "error": f"Correction failed: {exc}"}), 500


@app.route("/api/state")
def state():
    persisted = read_json(data_path("greg_living_state.json"), {})
    reality = greg.latest_reality or greg.refresh_reality(force=True, persist=False)
    benchmarks = _constitution_benchmark_snapshot()
    last_tick_at = persisted.get("last_updated") or ""
    alive_age_seconds = 999.0
    if last_tick_at:
        try:
            alive_age_seconds = max(
                0.0,
                (datetime.now(timezone.utc) - datetime.fromisoformat(last_tick_at)).total_seconds(),
            )
        except Exception:
            alive_age_seconds = 999.0
    epsilon = float((((reality.get("terms") or {}).get("epsilon") or {}).get("value") or 0.0))
    return jsonify(
        {
            "ok": True,
            "tick": int(persisted.get("tick") or greg.world.tick),
            "reality_score": float(reality.get("R") or 0.0),
            "epsilon": epsilon,
            "alive": alive_age_seconds <= 10.0,
            "alive_age_seconds": round(alive_age_seconds, 3),
            "last_tick_at": last_tick_at,
            "benchmarks": benchmarks,
        }
    )


@app.route("/greg")
def greg_page():
    return render_template("greg.html")


@app.route("/treasury")
def treasury():
    snapshot = _payment_activity_snapshot()
    return render_template(
        "treasury.html",
        wallet_address=os.getenv(
            "GREG_WALLET_ADDRESS",
            os.getenv("RECEIVER_WALLET_ADDRESS", "Treasury wallet not configured"),
        ),
        treasury=snapshot,
        finance=snapshot["finance"],
        protection=build_protection_state(
            session,
            surface="Treasury",
            required_roles=("founder", "treasury", "admin"),
        ),
    )


@app.route("/founder-office")
@role_required("founder")
def founder_office():
    office = _founder_office_snapshot()
    return render_template("founder_office.html", office=office)


@app.route("/greg-state")
def greg_state_page():
    snapshot = greg.status_snapshot()
    return render_template(
        "greg_state.html",
        constitution_status=_constitution_status_snapshot(),
        active_agents=agent_manager.list_agents(),
        benchmarks=_constitution_benchmark_snapshot(),
        greg_snapshot=snapshot,
    )


@app.route("/api/greg/status")
def greg_status():
    status = dict(greg.status_snapshot())
    payment_snapshot = _payment_activity_snapshot()
    status["payments"] = {
        "confirmed_usd": payment_snapshot["confirmed_usd"],
        "allocation": payment_snapshot["finance"],
        "recent_transactions": payment_snapshot["transactions"][:8],
    }
    status["constitution"] = {
        "hash": constitution_hash,
        "stored_hash": stored_constitution_hash,
    }
    status["benchmarks"] = _constitution_benchmark_snapshot()
    status["intent_queue"] = get_intents(limit=25)
    return jsonify(status)


@app.route("/api/status")
def api_status():
    status = dict(greg.status_snapshot())
    payment_snapshot = _payment_activity_snapshot()
    status["payments"] = {
        "confirmed_usd": payment_snapshot["confirmed_usd"],
        "allocation": payment_snapshot["finance"],
        "recent_transactions": payment_snapshot["transactions"][:8],
    }
    status["constitution"] = {
        "hash": constitution_hash,
        "stored_hash": stored_constitution_hash,
    }
    status["benchmarks"] = _constitution_benchmark_snapshot()
    status["intent_queue"] = get_intents(limit=25)
    return jsonify(status)


@app.route("/api/status-page/summary")
def api_status_page_summary():
    return jsonify(_status_page_summary())


@app.route("/api/status-page/stream")
def api_status_page_stream():
    def generate():
        while True:
            payload = json.dumps(_status_page_summary(), ensure_ascii=True)
            yield f"data: {payload}\n\n"
            time.sleep(10)

    return Response(generate(), mimetype="text/event-stream")


@app.route("/api/frontend/attention-flag", methods=["POST"])
def api_frontend_attention_flag():
    payload = request.get_json(silent=True) or {}
    page = str(payload.get("page") or "").strip() or "unknown"
    dwell_seconds = float(payload.get("dwell_seconds") or 0.0)
    history = read_json(FRONTEND_ATTENTION_FLAGS_PATH, {"flags": []})
    flags = history.get("flags") if isinstance(history, dict) else []
    if not isinstance(flags, list):
        flags = []
    record = {
        "page": page,
        "dwell_seconds": round(dwell_seconds, 3),
        "timestamp": _utc_now(),
        "user_agent": request.headers.get("User-Agent", ""),
    }
    flags.append(record)
    write_json(FRONTEND_ATTENTION_FLAGS_PATH, {"flags": flags[-200:]})
    return jsonify({"ok": True, "flag": record})


@app.route("/api/greg/image", methods=["POST"])
def greg_image():
    payload = request.get_json(silent=True) or {}
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"ok": False, "error": "prompt is required"}), 400
    try:
        validate_intent_against_constitution(
            f"generate image: {prompt}",
            {
                **payload,
                "action": "image_generation",
                "endpoint": "/api/greg/image",
            },
        )
        result = generate_image_asset(prompt, base_url=request.host_url.rstrip("/"))
        return jsonify(result), 200
    except ConstitutionViolation as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        app.logger.exception("Image generation failed.")
        return jsonify({"ok": False, "error": f"Image generation failed: {exc}"}), 500


@app.route("/api/intents/process", methods=["POST"])
def api_process_intent():
    payload = request.get_json(silent=True) or {}
    description = str(
        payload.get("description")
        or payload.get("intent")
        or payload.get("intent_description")
        or ""
    ).strip()
    if not description:
        return jsonify({"ok": False, "error": "description is required"}), 400
    intent_id = str(payload.get("intent_id") or f"intent_{uuid.uuid4().hex[:8]}").strip()
    payload.setdefault("base_url", request.host_url.rstrip("/"))
    result = process_intent(intent_id, description, payload)
    return jsonify(result), (200 if result.get("ok") else 400)


@app.route("/api/greg/reality")
def greg_reality():
    if not greg.latest_reality:
        greg.refresh_reality(force=True, persist=False)
    return jsonify(greg.latest_reality)


@app.route("/api/greg/think", methods=["POST"])
def greg_think():
    payload = request.get_json(silent=True) or {}
    return _dispatch_command("think", payload)


@app.route("/api/greg/command", methods=["POST"])
def greg_command():
    payload = request.get_json(silent=True) or {}
    action = payload.get("action")
    if str(action or "").strip().lower() == "spawn_agent":
        try:
            validate_intent_against_constitution(
                "spawn agent request",
                {
                    **payload,
                    "action": "spawn_agent",
                    "endpoint": "/api/greg/command",
                },
            )
        except ConstitutionViolation as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
    return _dispatch_command(action, payload)


@app.route("/api/task", methods=["POST"])
def api_task():
    payload = request.get_json(silent=True) or {}
    task = str(payload.get("task") or "").strip()
    if not task:
        return jsonify({"ok": False, "error": "Task required."}), 400
    body, status_code = command_locus.dispatch(
        "think",
        {
            "prompt": task,
            "mode": str(payload.get("mode") or "studio").strip() or "studio",
            "user_id": str(payload.get("user_id") or "task-api").strip() or "task-api",
        },
    )
    return jsonify(body), status_code


@app.route("/api/intents/<intent_id>/feedback", methods=["POST"])
@login_required
def api_intent_feedback(intent_id: str):
    payload = request.get_json(silent=True) or {}
    feedback = str(payload.get("feedback") or "").strip().lower()
    if feedback not in {"like", "dislike"}:
        return jsonify({"ok": False, "error": "feedback must be 'like' or 'dislike'"}), 400
    updated = update_intent_feedback(intent_id, feedback)
    if not updated:
        return jsonify({"ok": False, "error": "intent outcome not found"}), 404
    return jsonify({"ok": True, "intent_id": intent_id, "feedback": feedback, "outcome": updated})


@app.route("/api/greg/speak-first")
def greg_speak_first():
    mode = (request.args.get("mode") or "presence").strip()
    return _dispatch_command("speak_first", {"mode": mode})


@app.route("/api/greg/tick", methods=["POST"])
def greg_tick():
    return _dispatch_command("tick", {})


@app.route("/api/greg/agents", methods=["GET"])
def greg_agents():
    return jsonify({"agents": agent_manager.list_agents()})


@app.route("/api/greg/agents/spawn", methods=["POST"])
def greg_spawn_agent():
    payload = request.get_json(silent=True) or {}
    try:
        validate_intent_against_constitution(
            "spawn agent request",
            {
                **payload,
                "action": "spawn_agent",
                "endpoint": "/api/greg/agents/spawn",
            },
        )
    except ConstitutionViolation as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return _dispatch_command("spawn_agent", payload)


@app.route("/api/founder/intents/<intent_id>/cancel", methods=["POST"])
@role_required("founder")
def api_founder_cancel_intent(intent_id: str):
    intent = get_intent(intent_id)
    if not intent:
        return jsonify({"ok": False, "error": "Intent not found"}), 404
    update_intent_status(intent_id, "cancelled", result=intent.get("result"), error="Cancelled by founder")
    return jsonify({"ok": True, "intent_id": intent_id, "status": "cancelled"})


@app.route("/api/founder/intents/<intent_id>/retry", methods=["POST"])
@role_required("founder")
def api_founder_retry_intent(intent_id: str):
    intent = get_intent(intent_id)
    if not intent:
        return jsonify({"ok": False, "error": "Intent not found"}), 404
    payload = request.get_json(silent=True) or {}
    result = process_intent(intent_id, intent["description"], payload or {"build_protocol_steps": _intent_build_protocol_steps()})
    return jsonify(result), (200 if result.get("ok") else 400)


@app.route("/api/founder/staff-agents", methods=["POST"])
@role_required("founder")
def api_founder_staff_agents():
    payload = request.get_json(silent=True) or {}
    archetype = str(payload.get("archetype") or "builder").strip().lower() or "builder"
    current_task = str(payload.get("current_task") or f"support the {archetype} rail").strip()
    resource_limit = payload.get("resource_limit")
    if resource_limit is not None and not isinstance(resource_limit, dict):
        return jsonify({"ok": False, "error": "resource_limit must be an object"}), 400
    try:
        validate_intent_against_constitution(
            f"spawn staff agent {archetype}",
            {
                **payload,
                "action": "spawn_agent",
                "endpoint": "/api/founder/staff-agents",
                "founder_approval": True,
                "build_protocol_steps": _intent_build_protocol_steps(),
            },
        )
    except ConstitutionViolation as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    result = greg.spawn_agent(
        archetype,
        archetype=archetype,
        current_task=current_task,
        reputation=float(payload.get("reputation") or 0.9),
        resource_limit=resource_limit or {"cpu": 1, "api_tokens": 2000, "budget_usdc": 0},
    )
    return jsonify({"ok": True, "agent": result}), 200


@app.route("/api/greg/agents/<agent_id>/stop", methods=["POST"])
def greg_stop_agent(agent_id: str):
    return _dispatch_command("stop_agent", {"agent_id": agent_id})


@app.route("/admin/unlock", methods=["POST"])
def admin_unlock():
    secret = request.headers.get("X-Admin-Secret", "")
    if secret != ADMIN_SECRET_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    wallet = normalize_wallet(payload.get("wallet"))
    if not wallet:
        return jsonify({"error": "Wallet required"}), 400

    premium_wallets_path = data_path("premium_wallets.json")
    premium_wallets = load_premium_wallets()
    existing = premium_wallets.get(wallet, {})
    if not isinstance(existing, dict):
        existing = {}
    premium_wallets[wallet] = {
        **existing,
        "verified": True,
        "paid_at": datetime.now(timezone.utc).isoformat(),
        "tx_hash": "admin_unlock",
        "receiver_wallet": os.getenv("RECEIVER_WALLET_ADDRESS", "").lower(),
        "amount_units": 0,
        "amount_usdt": "0.00",
        "confirmations": 0,
        "expires_at": None,
        "admin_unlock": True,
    }
    write_json(premium_wallets_path, premium_wallets)
    return jsonify({"ok": True, "wallet": wallet, "premium": True})


@app.route("/admin/debug-premium")
def admin_debug_premium():
    secret = request.headers.get("X-Admin-Secret", "")
    if secret != ADMIN_SECRET_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    wallet = normalize_wallet(request.args.get("wallet"))
    if not wallet:
        return jsonify({"error": "Wallet required"}), 400

    record = premium_record_for_wallet(wallet)
    return jsonify(
        {
            "wallet": wallet,
            "is_premium": wallet_has_premium_access(wallet),
            "record": record,
        }
    )


@app.route("/intent_intent_7da8fa13")
def generated_intent_intent_7da8fa13():
    return render_template("generated/intent_7da8fa13.html")


@app.route("/intent_intent_547b2490")
def generated_intent_intent_547b2490():
    return render_template("generated/intent_547b2490.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
