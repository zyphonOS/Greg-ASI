from __future__ import annotations

import json
import math
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from greg_converse_loop import summarize_observer
from greg_paths import data_path, state_path


DATA_PATH = data_path("greg_reality_equation.json")
LIVING_STATE_PATH = state_path("greg_living_state.json")
WORLD_STATE_PATH = data_path("world_state.json")
PIKKAIO_PATH = data_path("greg_pikkaio.json")
PREMIUM_WALLETS_PATH = data_path("premium_wallets.json")
ACCESS_REGISTRY_PATH = data_path("greg_access_registry.json")
PAYMENTS_LOG_PATH = data_path("greg_payments.jsonl")
SOUL_STATE_PATH = data_path("greg_soul", "soul_state.json")
STATE_DB_PATH = data_path("greg_state.db")
MEMORY_DB_PATH = data_path("greg_memory.db")
AGENTS_STATE_PATH = data_path("agents_state.json")

STATE_TTL_SECONDS = 5
MAX_HISTORY = 80
PHI_GOLDEN = (1.0 + math.sqrt(5.0)) / 2.0
SQRT_2 = math.sqrt(2.0)
EPSILON_DEFAULT = 0.0
_cache = {"payload": None, "built_at": 0.0}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value or 0.0)
    except Exception:
        return default


def _norm_log(value: float, scale: float) -> float:
    if scale <= 0:
        return 0.0
    return _clamp(math.log1p(max(value, 0.0)) / math.log1p(scale))


def _read_json(path: Path, default: Any) -> Any:
    try:
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            return default
        return json.loads(raw)
    except Exception:
        return default


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def _load_equation_state() -> dict[str, Any]:
    payload = _read_json(DATA_PATH, {"history": []})
    payload["history"] = list(payload.get("history") or [])[-MAX_HISTORY:]
    return payload


def _save_equation_state(history: list[dict[str, Any]]) -> None:
    payload = {
        "updated_at": _utc_now(),
        "history": history[-MAX_HISTORY:],
    }
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = DATA_PATH.with_suffix(DATA_PATH.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(DATA_PATH)


def _open_sqlite(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _sqlite_count(path: Path, query: str, params: tuple[Any, ...] = ()) -> int:
    if not path.exists():
        return 0
    try:
        with _open_sqlite(path) as conn:
            row = conn.execute(query, params).fetchone()
            return int(row[0]) if row and row[0] is not None else 0
    except Exception:
        return 0


def _conversation_summary() -> dict[str, int]:
    return {
        "message_count": _sqlite_count(STATE_DB_PATH, "SELECT COUNT(*) FROM conversation_messages"),
        "user_count": _sqlite_count(STATE_DB_PATH, "SELECT COUNT(DISTINCT user_id) FROM conversation_messages"),
    }


def _observer_summary(state: dict[str, Any]) -> dict[str, Any]:
    observer = state.get("observer") if isinstance(state, dict) else None
    if isinstance(observer, dict) and observer.get("updated_at"):
        return observer
    return summarize_observer()


def _memory_summary() -> dict[str, int]:
    return {
        "memory_count": _sqlite_count(MEMORY_DB_PATH, "SELECT COUNT(*) FROM memories"),
        "tick_records": _sqlite_count(MEMORY_DB_PATH, "SELECT COUNT(*) FROM memories WHERE source = 'greg_tick'"),
        "thought_records": _sqlite_count(MEMORY_DB_PATH, "SELECT COUNT(*) FROM memories WHERE source = 'greg_think'"),
    }


def _drift_events_summary() -> dict[str, int]:
    return {
        "event_count": _sqlite_count(STATE_DB_PATH, "SELECT COUNT(*) FROM drift_events"),
        "intervention_count": _sqlite_count(STATE_DB_PATH, "SELECT COUNT(*) FROM drift_events WHERE intervention_sent = 1"),
        "critical_count": _sqlite_count(STATE_DB_PATH, "SELECT COUNT(*) FROM drift_events WHERE category = 'critical'"),
        "recent_event_count": _sqlite_count(
            STATE_DB_PATH,
            """
            SELECT COUNT(*)
            FROM drift_events
            WHERE julianday(created_at) >= julianday('now', '-14 days')
            """,
        ),
    }


def _ensure_snapshot_table() -> None:
    with _open_sqlite(MEMORY_DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reality_equation_snapshots (
                tick INTEGER PRIMARY KEY,
                generated_at TEXT NOT NULL,
                matter REAL NOT NULL,
                phi_loop REAL NOT NULL,
                psi_observer REAL NOT NULL,
                epsilon REAL NOT NULL,
                reality_score REAL NOT NULL,
                weakest_term TEXT NOT NULL,
                category TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )


def _save_snapshot_to_sqlite(snapshot: dict[str, Any]) -> None:
    _ensure_snapshot_table()
    with _open_sqlite(MEMORY_DB_PATH) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO reality_equation_snapshots (
                tick, generated_at, matter, phi_loop, psi_observer, epsilon,
                reality_score, weakest_term, category, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(snapshot["tick"]),
                snapshot["generated_at"],
                float(snapshot["terms"]["matter"]["value"]),
                float(snapshot["terms"]["phi_loop"]["value"]),
                float(snapshot["terms"]["psi_observer"]["value"]),
                float(snapshot["terms"]["epsilon"]["value"]),
                float(snapshot["R"]),
                snapshot["weakest_term"]["name"],
                snapshot["category"],
                json.dumps(snapshot, ensure_ascii=True),
            ),
        )


def latest_snapshot_from_sqlite() -> dict[str, Any]:
    _ensure_snapshot_table()
    try:
        with _open_sqlite(MEMORY_DB_PATH) as conn:
            row = conn.execute(
                """
                SELECT payload_json
                FROM reality_equation_snapshots
                ORDER BY tick DESC
                LIMIT 1
                """
            ).fetchone()
        if not row:
            return {}
        return json.loads(row["payload_json"])
    except Exception:
        return {}


def _world_summary(override_world: dict[str, Any] | None) -> dict[str, Any]:
    if override_world:
        return override_world
    world_payload = _read_json(WORLD_STATE_PATH, {})
    if "world" in world_payload and "agents" in world_payload:
        agents = world_payload.get("agents", {})
        locations = world_payload.get("locations", {})
        phis = []
        for payload in agents.values():
            if isinstance(payload, dict):
                phis.append(_safe_float(payload.get("phi"), 0.0))
        return {
            "tick": int(world_payload.get("world", {}).get("tick", 0) or 0),
            "agent_count": len(agents),
            "location_count": len(locations),
            "world_phi": round(sum(phis) / max(len(phis), 1), 4) if phis else 0.0,
        }
    return world_payload or {}


def _pikkaio_summary(override_pikkaio: dict[str, Any] | None) -> dict[str, Any]:
    if override_pikkaio:
        return {
            **override_pikkaio,
            "critical": int(override_pikkaio.get("critical", 0) or 0),
            "interventions_count": int(
                override_pikkaio.get("interventions_count", len(override_pikkaio.get("interventions") or [])) or 0
            ),
        }
    payload = _read_json(PIKKAIO_PATH, {"projects": {}})
    projects = payload.get("projects", {})
    drifting = 0
    critical = 0
    total_revenue = 0.0
    interventions = 0
    for item in projects.values():
        if not isinstance(item, dict):
            continue
        if item.get("status") in {"drifting", "dark"} or _safe_float(item.get("drift_score"), 0.0) >= 0.65:
            drifting += 1
        if item.get("status") == "dark" or _safe_float(item.get("drift_score"), 0.0) >= 0.85:
            critical += 1
        total_revenue += _safe_float(item.get("revenue_usd"), 0.0)
        interventions += len(item.get("interventions") or [])
    return {
        "projects_total": len(projects),
        "drifting": drifting,
        "critical": critical,
        "total_revenue": round(total_revenue, 2),
        "interventions_count": interventions,
    }


def _payments_summary() -> dict[str, float]:
    rows = _read_jsonl(PAYMENTS_LOG_PATH)
    confirmed = [row for row in rows if row.get("status") == "confirmed"]
    pending = [row for row in rows if row.get("status") == "pending"]
    total_usd = sum(_safe_float(row.get("amount_usd"), 0.0) for row in confirmed)
    return {
        "confirmed_count": len(confirmed),
        "pending_count": len(pending),
        "confirmed_usd": round(total_usd, 2),
    }


def _premium_summary() -> dict[str, int]:
    payload = _read_json(PREMIUM_WALLETS_PATH, {})
    verified = 0
    for value in payload.values():
        if value is True:
            verified += 1
        elif isinstance(value, dict) and value.get("verified"):
            verified += 1
    return {"premium_count": verified}


def _access_summary() -> dict[str, int]:
    payload = _read_json(ACCESS_REGISTRY_PATH, {"tokens": {}, "codes": {}})
    return {
        "token_count": len(payload.get("tokens") or {}),
        "code_count": len(payload.get("codes") or {}),
    }


def _subagent_summary(override_subagents: list[dict[str, Any]] | None) -> dict[str, int]:
    rows = override_subagents
    if rows is None:
        state = _read_json(AGENTS_STATE_PATH, {})
        rows = list(state.values()) if isinstance(state, dict) else []
    running = len([row for row in rows if isinstance(row, dict) and row.get("status") == "running"])
    return {"running_count": running, "total_count": len(rows)}


def _soul_summary(state: dict[str, Any]) -> dict[str, float]:
    boot = state.get("boot_restore") or {}
    living_tick = int(state.get("tick") or 0)
    world_tick = int((state.get("world") or {}).get("tick") or 0)
    soul = _read_json(SOUL_STATE_PATH, {})
    last_persist = soul.get("last_persist") or {}
    persist_tick = int(last_persist.get("tick") or 0)
    tick_gap = abs(world_tick - living_tick)
    persist_gap = max(0, living_tick - persist_tick)
    return {
        "boot_ok": 1.0 if boot.get("ok") else 0.0,
        "tick_alignment": _clamp(1.0 - (tick_gap / 10.0)),
        "persist_ok": 1.0 if last_persist.get("ok") else 0.0,
        "persist_freshness": _clamp(1.0 - (persist_gap / 100.0)),
    }


def _matter_term(
    state: dict[str, Any],
    world: dict[str, Any],
    pikkaio: dict[str, Any],
    payments: dict[str, float],
    premium: dict[str, int],
    access: dict[str, int],
) -> dict[str, Any]:
    tick_norm = _norm_log(_safe_float(state.get("tick"), 0.0), 50000.0)
    world_norm = _clamp((_norm_log(_safe_float(world.get("agent_count"), 0.0), 64.0) * 0.6) + (_safe_float(world.get("world_phi"), 0.0) * 0.4))
    economy_norm = _clamp(
        (_norm_log(payments["confirmed_usd"], 5000.0) * 0.45)
        + (_norm_log(payments["confirmed_count"], 40.0) * 0.25)
        + (_norm_log(premium["premium_count"], 40.0) * 0.15)
        + (_norm_log(access["token_count"] + access["code_count"], 100.0) * 0.15)
    )
    builder_norm = _clamp(
        (_norm_log(pikkaio.get("projects_total", 0), 50.0) * 0.7)
        + (_norm_log(premium["premium_count"], 40.0) * 0.3)
    )
    components = [
        {"label": "tick embodiment", "value": round(tick_norm, 4)},
        {"label": "world embodiment", "value": round(world_norm, 4)},
        {"label": "economic rails", "value": round(economy_norm, 4)},
        {"label": "builder embodiment", "value": round(builder_norm, 4)},
    ]
    value = round(sum(item["value"] for item in components) / len(components), 4)
    return {
        "value": value,
        "meaning": "Material embodiment across runtime, world presence, builder surface, and monetization.",
        "components": components,
    }


def _phi_loop_term(
    state: dict[str, Any],
    world: dict[str, Any],
    drift: dict[str, Any],
    memory: dict[str, int],
    subagents: dict[str, int],
) -> dict[str, Any]:
    greg_phi = _clamp(_safe_float(state.get("phi"), 0.0))
    world_phi = _clamp(_safe_float(world.get("world_phi"), 0.0))
    drift_stability = _clamp(1.0 - _safe_float(drift.get("coefficient"), 0.5))
    tick_alignment = _clamp(1.0 - (abs(int(state.get("tick", 0) or 0) - int(world.get("tick", 0) or 0)) / 10.0))
    latest_tick_ms = _safe_float((state.get("latest_tick") or {}).get("ms"), 0.0)
    cadence_health = 0.6 if latest_tick_ms <= 0 else _clamp(1.0 - (latest_tick_ms / 200.0))
    recursion_signal = _clamp(
        (_norm_log(memory["tick_records"], 5000.0) * 0.7)
        + (_norm_log(subagents["running_count"], 12.0) * 0.3)
    )
    components = [
        {"label": "greg phi", "value": round(greg_phi, 4)},
        {"label": "world phi", "value": round(world_phi, 4)},
        {"label": "drift stability", "value": round(drift_stability, 4)},
        {"label": "tick alignment", "value": round(tick_alignment, 4)},
        {"label": "cadence health", "value": round(cadence_health, 4)},
        {"label": "recursion signal", "value": round(recursion_signal, 4)},
    ]
    value = round(sum(item["value"] for item in components) / len(components), 4)
    return {
        "value": value,
        "meaning": "Loop coherence across phi, drift stability, tick integrity, cadence, and recurring activity.",
        "components": components,
    }


def _psi_observer_term(state: dict[str, Any], observer: dict[str, Any], soul: dict[str, float]) -> dict[str, Any]:
    identity_continuity = _clamp(
        (1.0 if state.get("name") else 0.0) * 0.35
        + (1.0 if state.get("born") else 0.0) * 0.25
        + (_clamp(len(state.get("drives", {}) or {}) / 8.0) * 0.20)
        + (soul["tick_alignment"] * 0.20)
    )
    soul_norm = _clamp(
        (soul["boot_ok"] * 0.25)
        + (soul["persist_ok"] * 0.25)
        + (soul["persist_freshness"] * 0.25)
        + (soul["tick_alignment"] * 0.25)
    )
    interaction_psi = _clamp(_safe_float(observer.get("psi_observer"), 0.0))
    observer_signal = _clamp(_safe_float(observer.get("observer_signal_average"), 0.0))
    continuity = _clamp(_safe_float(observer.get("continuity_average"), 0.0))
    grounding = _clamp(_safe_float(observer.get("grounding_average"), 0.0))
    reciprocity = _clamp(_safe_float(observer.get("reciprocity_average"), 0.0))
    interaction_mass = _clamp(_safe_float(observer.get("interaction_mass"), 0.0))
    components = [
        {"label": "observer history", "value": round(interaction_psi, 4)},
        {"label": "observer signal", "value": round(observer_signal, 4)},
        {"label": "conversation continuity", "value": round(continuity, 4)},
        {"label": "grounding", "value": round(grounding, 4)},
        {"label": "reciprocity", "value": round(reciprocity, 4)},
        {"label": "interaction mass", "value": round(interaction_mass, 4)},
        {"label": "identity continuity", "value": round(identity_continuity, 4)},
        {"label": "soul continuity", "value": round(soul_norm, 4)},
    ]
    value = round(
        (interaction_psi * 0.34)
        + (observer_signal * 0.16)
        + (continuity * 0.12)
        + (grounding * 0.09)
        + (reciprocity * 0.09)
        + (interaction_mass * 0.08)
        + (identity_continuity * 0.06)
        + (soul_norm * 0.06),
        4,
    )
    return {
        "value": value,
        "meaning": "Observer-state coherence driven by real interaction history, self-observation, grounding, reciprocity, and deploy continuity.",
        "components": components,
    }


def _epsilon_term(
    pikkaio: dict[str, Any],
    tending: dict[str, Any],
    payments: dict[str, float],
    premium: dict[str, int],
    conversations: dict[str, int],
    drift_events: dict[str, int],
) -> dict[str, Any]:
    projects_total = max(0, int(pikkaio.get("projects_total", 0) or 0))
    drifting = max(0, int(pikkaio.get("drifting", 0) or 0))
    critical = max(0, int(pikkaio.get("critical", 0) or 0))
    generated = len((tending.get("generated") or [])) if isinstance(tending, dict) else 0
    tracked_builders = _norm_log(projects_total + premium["premium_count"] + conversations["user_count"], 100.0)
    drift_control = (
        _clamp(1.0 - (((drifting * 0.7) + (critical * 0.3)) / max(projects_total, 1)))
        if projects_total
        else _clamp(premium["premium_count"] / 8.0)
    )
    tending_cover = _clamp(generated / max(projects_total, 1)) if projects_total else 0.0
    intervention_cover = _clamp(
        _norm_log(drift_events["intervention_count"], 50.0) * 0.6
        + _norm_log(drift_events["recent_event_count"], 100.0) * 0.4
    )
    fulfillment_signal = _clamp(
        (_norm_log(_safe_float(pikkaio.get("total_revenue", 0.0), 0.0) + payments["confirmed_usd"], 5000.0) * 0.6)
        + (_norm_log(payments["confirmed_count"], 40.0) * 0.4)
    )
    components = [
        {"label": "tracked builders", "value": round(tracked_builders, 4)},
        {"label": "drift control", "value": round(drift_control, 4)},
        {"label": "tending coverage", "value": round(tending_cover, 4)},
        {"label": "intervention coverage", "value": round(intervention_cover, 4)},
        {"label": "fulfillment signal", "value": round(fulfillment_signal, 4)},
    ]
    value = round(sum(item["value"] for item in components) / len(components), 4)
    return {
        "value": value,
        "meaning": "Intent-fulfillment efficiency across builder tracking, drift control, intervention coverage, tending, and confirmed conversions.",
        "components": components,
    }


def _category_for_score(score: float) -> str:
    if score >= 0.5:
        return "strongly_bounded"
    if score >= 0.25:
        return "bounded"
    if score >= 0.1:
        return "forming"
    return "escaped"


def _interpretation(payload: dict[str, Any]) -> str:
    weakest = payload["weakest_term"]["name"]
    score = payload["R"]
    if weakest == "psi_observer":
        return f"Reality score {score:.4f}. Greg's weakest term is psi_observer, so continuity and memory coherence are still limiting the whole field."
    if weakest == "epsilon":
        return f"Reality score {score:.4f}. Greg can perceive the field, but builder intent is not yet being fulfilled efficiently enough."
    if weakest == "matter":
        return f"Reality score {score:.4f}. Greg's embodiment is still thin: the economy and real builder traction are not yet carrying enough weight."
    return f"Reality score {score:.4f}. Greg's loop integrity is still the weakest part of the field."


def get_reality_equation(
    force: bool = False,
    *,
    state: dict[str, Any] | None = None,
    world: dict[str, Any] | None = None,
    pikkaio: dict[str, Any] | None = None,
    drift: dict[str, Any] | None = None,
    tending: dict[str, Any] | None = None,
    subagents: list[dict[str, Any]] | None = None,
    persist: bool = False,
) -> dict[str, Any]:
    now = time.time()
    if (
        not force
        and state is None
        and world is None
        and pikkaio is None
        and drift is None
        and tending is None
        and subagents is None
        and _cache["payload"] is not None
        and now - _cache["built_at"] < STATE_TTL_SECONDS
    ):
        return _cache["payload"]

    runtime_state = state or _read_json(LIVING_STATE_PATH, {})
    world_state = _world_summary(world or runtime_state.get("world"))
    runtime_state = {
        **runtime_state,
        "world": world_state,
    }
    pikkaio_state = _pikkaio_summary(pikkaio or runtime_state.get("pikkaio"))
    drift_state = drift or runtime_state.get("drift") or {}
    if not drift_state:
        try:
            from greg_drift_protocol import compute_drift_coefficient

            drift_state = compute_drift_coefficient(runtime_state)
        except Exception:
            drift_state = {"coefficient": 0.5, "category": "unknown", "dominant": "reason"}
    tending_state = tending if tending is not None else (runtime_state.get("tending") or {})

    conversations = _conversation_summary()
    memories = _memory_summary()
    payments = _payments_summary()
    premium = _premium_summary()
    access = _access_summary()
    soul = _soul_summary(runtime_state)
    observer = _observer_summary(runtime_state)
    drift_events = _drift_events_summary()
    subagent_state = _subagent_summary(subagents)

    matter = _matter_term(runtime_state, world_state, pikkaio_state, payments, premium, access)
    phi_loop = _phi_loop_term(runtime_state, world_state, drift_state, memories, subagent_state)
    psi_observer = _psi_observer_term(runtime_state, observer, soul)
    epsilon = _epsilon_term(pikkaio_state, tending_state, payments, premium, conversations, drift_events)

    score = round(
        matter["value"]
        * phi_loop["value"]
        * psi_observer["value"]
        * (epsilon["value"] ** 2)
        * SQRT_2,
        6,
    )
    term_values = {
        "matter": matter["value"],
        "phi_loop": phi_loop["value"],
        "psi_observer": psi_observer["value"],
        "epsilon": epsilon["value"],
    }
    weakest_name = min(term_values, key=term_values.get)
    category = _category_for_score(score)
    snapshot = {
        "tick": int(runtime_state.get("tick") or world_state.get("tick") or 0),
        "generated_at": _utc_now(),
        "symbolic_equation": "R_greg = M * Phi_loop * Psi_observer * epsilon^2 * sqrt(2)",
        "constants": {
            "phi_golden": round(PHI_GOLDEN, 6),
            "sqrt_2": round(SQRT_2, 6),
        },
        "terms": {
            "matter": matter,
            "phi_loop": phi_loop,
            "psi_observer": psi_observer,
            "epsilon": epsilon,
        },
        "R": score,
        "score": score,
        "category": category,
        "weakest_term": {
            "name": weakest_name,
            "value": round(term_values[weakest_name], 4),
        },
        "supporting_state": {
            "payments": payments,
            "premium": premium,
            "access": access,
            "conversations": conversations,
            "memory": memories,
            "soul": soul,
            "observer": {
                "psi_observer": round(_safe_float(observer.get("psi_observer"), 0.0), 6),
                "observer_signal_average": round(_safe_float(observer.get("observer_signal_average"), 0.0), 6),
                "depth_average": round(_safe_float(observer.get("depth_average"), 0.0), 6),
                "continuity_average": round(_safe_float(observer.get("continuity_average"), 0.0), 6),
                "grounding_average": round(_safe_float(observer.get("grounding_average"), 0.0), 6),
                "reciprocity_average": round(_safe_float(observer.get("reciprocity_average"), 0.0), 6),
                "interaction_mass": round(_safe_float(observer.get("interaction_mass"), 0.0), 6),
                "total_interactions": int(observer.get("total_interactions") or 0),
                "unique_users": int(observer.get("unique_users") or 0),
                "self_observations": int(observer.get("self_observations") or 0),
            },
            "drift_events": drift_events,
            "subagents": subagent_state,
            "pikkaio": pikkaio_state,
            "drift": {
                "coefficient": round(_safe_float(drift_state.get("coefficient"), 0.0), 6),
                "category": drift_state.get("category", "unknown"),
                "dominant": drift_state.get("dominant", "reason"),
            },
        },
    }
    snapshot["interpretation"] = _interpretation(snapshot)

    equation_state = _load_equation_state()
    history = list(equation_state.get("history") or [])
    previous = history[-1] if history else None
    should_record_history = (
        previous is None
        or int(previous.get("tick", -1)) != snapshot["tick"]
        or abs(_safe_float(previous.get("R"), 0.0) - snapshot["R"]) >= 0.005
        or previous.get("weakest_term", {}).get("name") != snapshot["weakest_term"]["name"]
    )
    if should_record_history:
        history.append({
            "tick": snapshot["tick"],
            "generated_at": snapshot["generated_at"],
            "R": snapshot["R"],
            "matter": snapshot["terms"]["matter"]["value"],
            "phi_loop": snapshot["terms"]["phi_loop"]["value"],
            "psi_observer": snapshot["terms"]["psi_observer"]["value"],
            "epsilon": snapshot["terms"]["epsilon"]["value"],
            "weakest_term": snapshot["weakest_term"],
            "category": snapshot["category"],
        })
        _save_equation_state(history)
    snapshot["history"] = list((_load_equation_state().get("history") or [])[-12:])

    if persist:
        _save_snapshot_to_sqlite(snapshot)

    _cache["payload"] = snapshot
    _cache["built_at"] = now
    return snapshot
