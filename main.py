from __future__ import annotations

import ast
import hashlib
import json
import operator
import os
import re
import secrets
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
from flask import Blueprint, Flask, Response, jsonify, render_template, request

from core.agent_manager import manager as agent_manager
from core.command_locus import CommandLocus
from core.greg import Greg
from core.truth_surface import build_truth_surface
from core.utils import data_path, ensure_json_file, read_json, write_json
from intent_store import init_db as init_intent_db, save_intent, update_intent_status
from constitution_guard import ConstitutionViolation, validate_intent_against_constitution


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))
CONSTITUTION_PATH = os.path.join(BASE_DIR, "CONSTITUTION.md")
CONSTITUTION_LOG_PATH = os.path.join(BASE_DIR, "constitution_changed.log")

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

for error in _optional_import_errors:
    app.logger.warning(error)

app.register_blueprint(pingme_bp)
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

for path, default in {
    data_path("memory.json"): {},
    data_path("premium_wallets.json"): {},
    data_path("nonces.json"): {},
    data_path("leaderboard.json"): [],
    data_path("agents_state.json"): {},
    data_path("intents.json"): {"intents": []},
    data_path("constitution_state.json"): {"constitution_hash": ""},
    data_path("greg_pikkaio.json"): {"projects": {}},
    data_path("greg_access_registry.json"): {"tokens": {}, "codes": {}},
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


def _bootstrap_constitution_state() -> dict[str, Any]:
    current_text = _read_constitution_text()
    current_hash = _hash_constitution(current_text)
    state_path = data_path("constitution_state.json")
    state = read_json(state_path, {"constitution_hash": ""})
    stored_hash = str(state.get("constitution_hash") or "").strip()
    now = datetime.now(timezone.utc).isoformat()

    if not stored_hash:
        state = {
            "constitution_hash": current_hash,
            "last_seen_hash": current_hash,
            "last_checked_at": now,
            "tamper_detected": False,
        }
        write_json(state_path, state)
        return state

    state["last_seen_hash"] = current_hash
    state["last_checked_at"] = now
    state["tamper_detected"] = stored_hash != current_hash

    if stored_hash != current_hash:
        app.logger.warning(
            "Constitution hash mismatch detected. stored=%s current=%s",
            stored_hash,
            current_hash,
        )
        _append_constitution_change_notice(stored_hash, current_hash)

    write_json(state_path, state)
    return state


CONSTITUTION_TEXT = _read_constitution_text()
constitution_hash = _hash_constitution(CONSTITUTION_TEXT)
constitution_state = _bootstrap_constitution_state()
stored_constitution_hash = str(constitution_state.get("constitution_hash") or constitution_hash)

init_intent_db()
greg = Greg(memory_path=data_path("memory.json"))
command_locus = CommandLocus(greg=greg, agent_manager=agent_manager)
app.extensions["greg"] = greg
app.extensions["command_locus"] = command_locus
app.extensions["constitution_hash"] = constitution_hash
app.extensions["stored_constitution_hash"] = stored_constitution_hash


def _start_background_services() -> None:
    if app.extensions.get("greg_tick_started"):
        return
    if os.getenv("DISABLE_TICK_LOOP", "false").lower() == "true":
        app.logger.info("Greg tick loop disabled by DISABLE_TICK_LOOP=true.")
        return
    greg.start_background_tick()
    app.extensions["greg_tick_started"] = True


if os.environ.get("WERKZEUG_RUN_MAIN") in {None, "true"}:
    _start_background_services()


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

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return _mock_groq(prompt)

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
                {"role": "user", "content": prompt},
            ],
            max_tokens=256,
            temperature=0.2,
        )
        content = (completion.choices[0].message.content or "").strip()
        return content or _mock_groq(prompt)
    except Exception as exc:
        app.logger.warning("Groq call failed, using mock response: %s", exc)
        return _mock_groq(prompt)


def _dispatch_command(action: str, payload: dict | None = None):
    body, status_code = command_locus.dispatch(action, payload or {})
    return jsonify(body), status_code


def process_intent(intent_id: str, description: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    save_intent(intent_id, description, status="pending")

    try:
        validate_intent_against_constitution(description, payload)
        update_intent_status(intent_id, "running")

        generated_output = call_groq(description)
        result = {
            "ok": True,
            "intent_id": intent_id,
            "status": "completed",
            "result": generated_output,
            "constitution_hash": constitution_hash,
        }
        update_intent_status(intent_id, "completed", result=json.dumps(result), error=None)
        return result
    except ConstitutionViolation as exc:
        update_intent_status(intent_id, "failed", error=str(exc))
        return {
            "ok": False,
            "intent_id": intent_id,
            "status": "failed",
            "error": str(exc),
            "constitution_hash": constitution_hash,
        }
    except Exception as exc:
        update_intent_status(intent_id, "failed", error=str(exc))
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


@app.route("/truth")
def truth():
    try:
        return render_template("truth.html", truth=build_truth_surface(greg))
    except Exception:
        return jsonify({"ok": True, "truth": build_truth_surface(greg)})


@app.route("/api/health")
def health():
    return jsonify({"ok": True, "tick": greg.world.tick})


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


@app.route("/api/state")
def state():
    persisted = read_json(data_path("greg_living_state.json"), {})
    reality = greg.latest_reality or greg.refresh_reality(force=True, persist=False)
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
        }
    )


@app.route("/api/greg/status")
def greg_status():
    return jsonify(greg.status_snapshot())


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
    return _dispatch_command("spawn_agent", payload)


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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
