from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import quote

import requests
from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from core.utils import TTLCache, data_path, ensure_json_file, read_json, signature_message, verify_wallet_signature, write_json
from layers.intents.harvestiq.analysis_engine import (
    SUPPORTED_CHAINS,
    anonymize_wallet,
    build_report,
    get_chain_config,
    validate_wallet,
)


harvestiq_bp = Blueprint("harvestiq", __name__, template_folder="templates", static_folder="static")

BASE_DIR = Path(__file__).resolve().parent
NONCES_FILE = data_path("nonces.json")
PREMIUM_WALLETS_FILE = data_path("premium_wallets.json")
LEADERBOARD_FILE = data_path("leaderboard.json")

CACHE_TTL_SECONDS = 300
PAYMENT_CACHE_TTL_SECONDS = 12
NONCE_TTL_MINUTES = 15
REPORT_CACHE_LIMIT = 120
USDT_DECIMALS = 6
DEFAULT_PAYMENT_AMOUNT = Decimal("9.99")
USDT_CONTRACT = (os.getenv("USDT_CONTRACT_ADDRESS") or "0xdac17f958d2ee523a2206206994597c13d831ec7").lower()

EXPLORER_CACHE = TTLCache(ttl_seconds=CACHE_TTL_SECONDS)
REPORT_CACHE: dict[str, dict] = {}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc() -> str:
    return now_utc().isoformat()


def parse_decimal(value, fallback):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return fallback


PAYMENT_AMOUNT_USDT = parse_decimal(os.getenv("PREMIUM_PRICE_USDT", DEFAULT_PAYMENT_AMOUNT), DEFAULT_PAYMENT_AMOUNT)
PAYMENT_AMOUNT_UNITS = int(PAYMENT_AMOUNT_USDT * (10 ** USDT_DECIMALS))

ensure_json_file(NONCES_FILE, {})
ensure_json_file(PREMIUM_WALLETS_FILE, {})
ensure_json_file(LEADERBOARD_FILE, [])


def normalize_wallet(value: str | None) -> str:
    return (value or "").strip().lower()


def normalize_premium_record(record) -> dict | None:
    if isinstance(record, bool):
        return {
            "verified": record,
            "paid_at": None,
            "tx_hash": None,
            "receiver_wallet": None,
            "amount_units": 0,
            "amount_usdt": "0.00",
            "confirmations": 0,
            "expires_at": None,
            "admin_unlock": False,
        }
    if not isinstance(record, dict):
        return None

    normalized = dict(record)
    normalized["verified"] = bool(normalized.get("verified", normalized.get("admin_unlock", False)))
    normalized["tx_hash"] = normalized.get("tx_hash")
    if normalized["tx_hash"] is not None:
        normalized["tx_hash"] = str(normalized["tx_hash"]).lower()
    normalized["receiver_wallet"] = normalize_wallet(normalized.get("receiver_wallet"))
    normalized["amount_units"] = int(normalized.get("amount_units", 0) or 0)
    normalized["amount_usdt"] = str(normalized.get("amount_usdt", "0.00"))
    normalized["confirmations"] = int(normalized.get("confirmations", 0) or 0)
    normalized["expires_at"] = normalized.get("expires_at")
    normalized["admin_unlock"] = bool(normalized.get("admin_unlock", False))
    normalized["paid_at"] = normalized.get("paid_at")
    return normalized


def load_premium_wallets() -> dict[str, dict]:
    payload = read_json(PREMIUM_WALLETS_FILE, {})
    if not isinstance(payload, dict):
        payload = {}

    normalized_payload: dict[str, dict] = {}
    changed = False

    for wallet, record in payload.items():
        normalized_wallet = normalize_wallet(wallet)
        normalized_record = normalize_premium_record(record)
        if not normalized_wallet or normalized_record is None:
            changed = True
            continue
        if normalized_wallet in normalized_payload and normalized_payload[normalized_wallet].get("verified"):
            changed = True
            continue
        normalized_payload[normalized_wallet] = normalized_record
        if wallet != normalized_wallet or normalized_record != record:
            changed = True

    if changed:
        write_json(PREMIUM_WALLETS_FILE, normalized_payload)

    return normalized_payload


def premium_record_for_wallet(wallet: str | None) -> dict | None:
    normalized_wallet = normalize_wallet(wallet)
    if not normalized_wallet:
        return None
    return load_premium_wallets().get(normalized_wallet)


def receiver_wallet() -> str:
    return (os.getenv("RECEIVER_WALLET_ADDRESS") or "0xYourReceiverWallet").lower()


def app_base_url() -> str:
    return os.getenv("APP_BASE_URL", "https://harvestiq.app").rstrip("/")


def current_authenticated_wallet() -> str:
    wallet = session.get("authenticated_wallet")
    return normalize_wallet(wallet if isinstance(wallet, str) else "")


def wallet_has_premium_access(wallet: str | None) -> bool:
    wallet = normalize_wallet(wallet)
    if not wallet:
        return False
    record = premium_record_for_wallet(wallet)
    if not record:
        return False
    expires_at = record.get("expires_at")
    if expires_at:
        try:
            if datetime.fromisoformat(expires_at) < now_utc():
                return False
        except ValueError:
                return False
    return bool(record.get("verified"))


def has_premium_access(wallet: str | None = None) -> bool:
    return wallet_has_premium_access(wallet or current_authenticated_wallet())


def sync_session_premium_flag() -> None:
    session["premium_access"] = has_premium_access()
    session.modified = True


def get_report(report_id: str | None):
    if not report_id:
        return None
    return REPORT_CACHE.get(report_id)


def store_report(report: dict) -> dict:
    report_id = hashlib.sha256(f"{report['address']}:{report['chain']}:{time.time_ns()}".encode("utf-8")).hexdigest()[:16]
    report["id"] = report_id
    REPORT_CACHE[report_id] = report
    while len(REPORT_CACHE) > REPORT_CACHE_LIMIT:
        oldest_key = next(iter(REPORT_CACHE))
        REPORT_CACHE.pop(oldest_key, None)
    return report


def session_list(key: str) -> list:
    value = session.get(key, [])
    return value if isinstance(value, list) else []


def upsert_session_entry(key: str, entry: dict, limit: int = 10) -> None:
    entries = session_list(key)
    entries = [
        item for item in entries
        if not (
            item.get("address") == entry.get("address") and
            item.get("chain") == entry.get("chain")
        )
    ]
    entries.insert(0, entry)
    session[key] = entries[:limit]
    session.modified = True


def save_wallet_to_session(address: str, chain: str, source: str = "saved") -> None:
    upsert_session_entry(
        "saved_wallets",
        {
            "address": address.lower(),
            "chain": chain,
            "chain_label": get_chain_config(chain)["label"],
            "source": source,
            "saved_at": iso_utc(),
        },
        limit=15,
    )


def record_scan_history(report: dict) -> None:
    upsert_session_entry(
        "scan_history",
        {
            "address": report["address"],
            "chain": report["chain"],
            "chain_label": report["chain_label"],
            "score": report["score"],
            "risk_level": report["risk_level"],
            "report_id": report["id"],
            "generated_at": report["generated_at"],
        },
        limit=12,
    )


def update_leaderboard(report: dict) -> None:
    rows = read_json(LEADERBOARD_FILE, [])
    if not isinstance(rows, list):
        rows = []

    entry = {
        "address": report["address"],
        "address_masked": anonymize_wallet(report["address"]),
        "score": report["score"],
        "risk_level": report["risk_level"],
        "chain": report["chain"],
        "chain_label": report["chain_label"],
        "generated_at": report["generated_at"],
    }
    rows = [row for row in rows if not (row.get("address") == report["address"] and row.get("chain") == report["chain"])]
    rows.append(entry)
    rows.sort(key=lambda item: (item.get("score", 1000), item.get("generated_at", "")))
    write_json(LEADERBOARD_FILE, rows[:50])


def leaderboard_rows() -> list[dict]:
    rows = read_json(LEADERBOARD_FILE, [])
    if not isinstance(rows, list):
        rows = []
    return sorted(rows, key=lambda item: (item.get("score", 1000), item.get("generated_at", "")))[:10]


def explorer_cache_key(chain: str, params: dict) -> str:
    return json.dumps([chain, sorted(params.items())], sort_keys=True)


def explorer_request(chain: str, params: dict, ttl_seconds: int = CACHE_TTL_SECONDS, allow_stale: bool = True):
    key = explorer_cache_key(chain, params)
    cached = EXPLORER_CACHE.get(key)
    if cached is not None:
        return cached, {"status": "ok", "cached": True, "message": "cached"}

    chain_config = get_chain_config(chain)
    api_key = os.getenv(chain_config["api_key_env"]) or os.getenv("ETHERSCAN_API_KEY", "")
    full_params = dict(params)
    if api_key:
        full_params["apikey"] = api_key

    try:
        response = requests.get(chain_config["api_url"], params=full_params, timeout=18)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        if allow_stale and cached is not None:
            return cached, {"status": "stale", "cached": True, "message": "stale cache"}
        return None, {"status": "error", "cached": False, "message": "Explorer request failed"}

    result = payload.get("result")
    if payload.get("status") == "0" and "rate limit" in str(result).lower():
        if allow_stale and cached is not None:
            return cached, {"status": "rate_limited", "cached": True, "message": "rate limited, serving cache"}
        return None, {"status": "rate_limited", "cached": False, "message": "Explorer rate limit reached"}

    EXPLORER_CACHE.set(key, payload, ttl_seconds=ttl_seconds)
    return payload, {"status": "ok", "cached": False, "message": payload.get("message", "OK")}


def fetch_transactions(address: str, chain: str = "eth", limit: int = 200):
    payload, meta = explorer_request(
        chain,
        {
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": 0,
            "endblock": 99999999,
            "page": 1,
            "offset": limit,
            "sort": "asc",
        },
    )
    if not payload:
        return [], meta
    result = payload.get("result", [])
    if isinstance(result, list):
        return result, meta
    return [], {"status": meta["status"], "cached": meta["cached"], "message": str(result or payload.get("message") or "No transactions returned")}


def fetch_token_transfers(address: str, limit: int = 100, refresh: bool = False):
    payload, meta = explorer_request(
        "eth",
        {
            "module": "account",
            "action": "tokentx",
            "address": address,
            "contractaddress": USDT_CONTRACT,
            "page": 1,
            "offset": limit,
            "sort": "desc",
        },
        ttl_seconds=1 if refresh else PAYMENT_CACHE_TTL_SECONDS,
        allow_stale=not refresh,
    )
    if not payload:
        return [], meta
    result = payload.get("result", [])
    if isinstance(result, list):
        return result, meta
    return [], {"status": meta["status"], "cached": meta["cached"], "message": str(result or payload.get("message") or "No token transfers returned")}


def fetch_cross_chain_activity(address: str, primary_chain: str):
    activity = []
    for chain, config in SUPPORTED_CHAINS.items():
        if chain == primary_chain:
            continue
        txs, meta = fetch_transactions(address, chain=chain, limit=60)
        activity.append(
            {
                "chain": chain,
                "label": config["label"],
                "tx_count": len(txs),
                "first_seen": int(txs[0].get("timeStamp", 0) or 0) if txs else 0,
                "last_seen": int(txs[-1].get("timeStamp", 0) or 0) if txs else 0,
                "status": meta["status"],
                "transactions": txs[:25],
            }
        )
    return activity


def issue_nonce(address: str) -> str:
    nonce = secrets.token_hex(16)
    payload = read_json(NONCES_FILE, {})
    payload[address.lower()] = {
        "nonce": nonce,
        "created_at": iso_utc(),
        "expires_at": (now_utc() + timedelta(minutes=NONCE_TTL_MINUTES)).isoformat(),
    }
    write_json(NONCES_FILE, payload)
    return nonce


def valid_nonce(address: str, nonce: str) -> bool:
    payload = read_json(NONCES_FILE, {})
    record = payload.get(address.lower())
    if not record or record.get("nonce") != nonce:
        return False
    try:
        return datetime.fromisoformat(record["expires_at"]) > now_utc()
    except (KeyError, ValueError):
        return False


def consume_nonce(address: str) -> None:
    payload = read_json(NONCES_FILE, {})
    payload.pop(address.lower(), None)
    write_json(NONCES_FILE, payload)


def mark_authenticated_wallet(address: str) -> None:
    session["authenticated_wallet"] = normalize_wallet(address)
    session.modified = True
    sync_session_premium_flag()


def mark_wallet_premium(address: str, tx_hash: str, transfer: dict) -> None:
    payload = load_premium_wallets()
    payload[normalize_wallet(address)] = {
        "verified": True,
        "paid_at": iso_utc(),
        "tx_hash": tx_hash.lower(),
        "receiver_wallet": receiver_wallet(),
        "amount_units": int(transfer.get("value", 0) or 0),
        "amount_usdt": f"{Decimal(int(transfer.get('value', 0) or 0)) / (10 ** USDT_DECIMALS):.2f}",
        "confirmations": int(transfer.get("confirmations", 0) or 0),
        "expires_at": None,
    }
    write_json(PREMIUM_WALLETS_FILE, payload)
    sync_session_premium_flag()


def payment_status(address: str, tx_hash: str | None = None, refresh: bool = False) -> dict:
    wallet = normalize_wallet(address)
    if wallet_has_premium_access(wallet):
        return {"status": "confirmed", "message": "Premium access already active for this wallet."}
    if not tx_hash:
        return {"status": "awaiting_tx", "message": "Waiting for a USDT transaction hash."}

    transfers, meta = fetch_token_transfers(wallet, refresh=refresh)
    if not transfers:
        return {
            "status": "checking" if meta["status"] in {"ok", "stale", "rate_limited"} else "error",
            "message": "No USDT transfers found yet for this wallet.",
            "api_status": meta,
        }

    for transfer in transfers:
        if (transfer.get("hash") or "").lower() != tx_hash.lower():
            continue
        from_wallet = (transfer.get("from") or "").lower()
        to_wallet = (transfer.get("to") or "").lower()
        contract = (transfer.get("contractAddress") or "").lower()
        confirmations = int(transfer.get("confirmations", 0) or 0)
        value = int(transfer.get("value", 0) or 0)

        if from_wallet != wallet:
            return {"status": "failed", "message": "The payment transaction was not sent from the connected wallet."}
        if to_wallet != receiver_wallet():
            return {"status": "failed", "message": "The payment transaction was not sent to the HarvestIQ receiver wallet."}
        if contract != USDT_CONTRACT:
            return {"status": "failed", "message": "The transaction is not an Ethereum USDT transfer."}
        if value < PAYMENT_AMOUNT_UNITS:
            return {"status": "failed", "message": f"The transfer is below the required {PAYMENT_AMOUNT_USDT} USDT."}
        if confirmations < 1:
            return {"status": "pending_confirmation", "message": "Payment found. Waiting for the first confirmation.", "confirmations": confirmations}
        return {
            "status": "confirmed",
            "message": "USDT payment confirmed on-chain.",
            "confirmations": confirmations,
            "transfer": transfer,
        }

    return {"status": "checking", "message": "Transaction not visible in the explorer response yet.", "api_status": meta}


def share_text_for_report(report: dict) -> str:
    return f"My HarvestIQ sybil score is {report['score']}/100 ({report['risk_level']}). Check yours before the next airdrop! {app_base_url()}"


def build_report_response(report: dict) -> dict:
    current_wallet = current_authenticated_wallet()
    report_wallet = normalize_wallet(report["address"])
    session_premium = has_premium_access()
    wallet_premium = wallet_has_premium_access(report_wallet)
    return {
        "report_id": report["id"],
        "address": report["address"],
        "chain": report["chain"],
        "chain_label": report["chain_label"],
        "score": report["score"],
        "risk_level": report["risk_level"],
        "summary": report["summary"],
        "components": [
            {
                "label": component["label"],
                "score": component["score"],
                "max_score": component["max_score"],
                "health_score": component["health_score"],
                "risk": component["risk"],
                "summary": component["summary"],
            }
            for component in report["components"]
        ],
        "recommendations": report["recommendations"],
        "premium_plan_preview": [item["action"] for item in report["premium_plan"][:2]],
        "totals": report["totals"],
        "generated_at": report["generated_at"],
        "api_status": report["api_status"],
        "premium_unlocked": session_premium,
        "wallet_premium_access": wallet_premium,
        "is_premium": session_premium or (wallet_premium and current_wallet == report_wallet),
        "premium_url": url_for("harvestiq.view_report", report_id=report["id"]),
        "share_text": share_text_for_report(report),
    }


def selected_report(report_id: str | None = None):
    if report_id:
        return get_report(report_id)
    latest = session.get("latest_report_id")
    return get_report(latest) if latest else None


def payload_from_request() -> dict:
    return request.get_json(silent=True) or request.form.to_dict()


@harvestiq_bp.route("/")
def index():
    return render_template(
        "index.html",
        chains=SUPPORTED_CHAINS,
        api_base=url_for("harvestiq.index").rstrip("/"),
        receiver_wallet=receiver_wallet(),
        payment_amount=str(PAYMENT_AMOUNT_USDT),
        usdt_contract=USDT_CONTRACT,
        app_url=app_base_url(),
        saved_wallets=session_list("saved_wallets"),
        recent_wallets=session_list("scan_history"),
        leaderboard=leaderboard_rows(),
        authenticated_wallet=current_authenticated_wallet(),
        premium_access=has_premium_access(),
    )


@harvestiq_bp.route("/payment")
def payment():
    report = selected_report(request.args.get("report_id"))
    return render_template(
        "payment.html",
        report=report,
        payment_amount=str(PAYMENT_AMOUNT_USDT),
        receiver_wallet=receiver_wallet(),
        usdt_contract=USDT_CONTRACT,
        authenticated_wallet=current_authenticated_wallet(),
        premium_access=has_premium_access(),
    )


@harvestiq_bp.route("/health")
def health():
    return jsonify({"ok": True, "timestamp": iso_utc()})


@harvestiq_bp.route("/session-state")
def session_state():
    sync_session_premium_flag()
    checked_wallet = normalize_wallet(request.args.get("wallet")) or current_authenticated_wallet()
    session_premium = has_premium_access()
    checked_wallet_premium = wallet_has_premium_access(checked_wallet)
    response = jsonify(
        {
            "authenticated_wallet": current_authenticated_wallet(),
            "premium_access": session_premium,
            "checked_wallet": checked_wallet,
            "checked_wallet_premium": checked_wallet_premium,
            "is_premium": session_premium or checked_wallet_premium,
            "saved_wallets": session_list("saved_wallets"),
            "scan_history": session_list("scan_history"),
            "leaderboard": leaderboard_rows(),
        }
    )
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


@harvestiq_bp.route("/analyze", methods=["POST"])
def analyze():
    data = payload_from_request()
    address = normalize_wallet(data.get("address"))
    chain = (data.get("chain") or "eth").strip().lower()
    if not validate_wallet(address):
        return jsonify({"error": "Enter a valid EVM wallet address."}), 400
    if chain not in SUPPORTED_CHAINS:
        return jsonify({"error": "Unsupported chain selected."}), 400

    transactions, api_meta = fetch_transactions(address, chain=chain, limit=220)
    cross_chain_activity = fetch_cross_chain_activity(address, chain)
    report = build_report(address, chain, transactions, cross_chain_activity, api_meta)
    report = store_report(report)

    session["latest_report_id"] = report["id"]
    session.modified = True
    record_scan_history(report)
    update_leaderboard(report)

    payload = build_report_response(report)
    payload["upsell_copy"] = (
        f"Your score is {report['score']}. That's {report['risk_level']} risk - you could still be excluded. "
        f"For ${PAYMENT_AMOUNT_USDT}, get the exact transaction hashes that hurt you, and a step-by-step plan "
        "to become 'human-like' before the next snapshot."
    )
    return jsonify(payload)


@harvestiq_bp.route("/auth/nonce", methods=["POST"])
def auth_nonce():
    data = payload_from_request()
    address = normalize_wallet(data.get("address"))
    if not validate_wallet(address):
        return jsonify({"error": "Connect a valid wallet address."}), 400
    nonce = issue_nonce(address)
    return jsonify({"nonce": nonce, "address": address, "message": signature_message(nonce)})


@harvestiq_bp.route("/auth/verify", methods=["POST"])
def auth_verify():
    data = payload_from_request()
    address = normalize_wallet(data.get("address"))
    signature = (data.get("signature") or "").strip()
    nonce = (data.get("nonce") or "").strip()

    if not validate_wallet(address):
        return jsonify({"error": "Invalid wallet address."}), 400
    if not signature or not nonce:
        return jsonify({"error": "Signature and nonce are required."}), 400
    if not valid_nonce(address, nonce):
        return jsonify({"error": "Nonce expired or invalid. Request a fresh signature."}), 400
    if not verify_wallet_signature(address, signature, nonce):
        return jsonify({"error": "Signature does not match the connected wallet."}), 401

    consume_nonce(address)
    mark_authenticated_wallet(address)
    latest = selected_report()
    latest_url = url_for("harvestiq.view_report", report_id=latest["id"]) if latest and has_premium_access() else ""
    return jsonify(
        {
            "ok": True,
            "address": address,
            "premium_access": has_premium_access(),
            "wallet_premium_access": wallet_has_premium_access(address),
            "is_premium": has_premium_access(address),
            "receiver_wallet": receiver_wallet(),
            "usdt_contract": USDT_CONTRACT,
            "payment_amount": str(PAYMENT_AMOUNT_USDT),
            "latest_report_url": latest_url,
            "message": "Wallet signature verified.",
        }
    )


@harvestiq_bp.route("/check-payment", methods=["POST"])
def check_payment():
    data = payload_from_request()
    address = normalize_wallet(data.get("address"))
    tx_hash = normalize_wallet(data.get("tx_hash"))
    report_id = (data.get("report_id") or session.get("latest_report_id") or "").strip()

    if current_authenticated_wallet() != address:
        return jsonify({"error": "Connect and sign with the wallet that sent the payment."}), 403
    if not tx_hash.startswith("0x"):
        return jsonify({"error": "Enter a valid transaction hash."}), 400

    status = payment_status(address, tx_hash=tx_hash, refresh=True)
    if status["status"] == "confirmed":
        mark_wallet_premium(address, tx_hash, status["transfer"])
        report = get_report(report_id)
        return jsonify(
            {
                "ok": True,
                "status": "confirmed",
                "message": status["message"],
                "report_url": url_for("harvestiq.view_report", report_id=report["id"]) if report else "",
                "premium_access": True,
            }
        )

    return jsonify(
        {
            "ok": False,
            "status": status["status"],
            "message": status["message"],
            "premium_access": has_premium_access(),
        }
    )


@harvestiq_bp.route("/payment-status")
def payment_status_route():
    address = normalize_wallet(request.args.get("address"))
    tx_hash = normalize_wallet(request.args.get("tx_hash"))
    if not address:
        return jsonify({"error": "Wallet address required."}), 400
    if current_authenticated_wallet() != address:
        return jsonify({"error": "Wallet mismatch for the active session."}), 403

    status = payment_status(address, tx_hash=tx_hash, refresh=True)
    if status["status"] == "confirmed":
        mark_wallet_premium(address, tx_hash, status["transfer"])
    return jsonify({"status": status["status"], "message": status["message"], "premium_access": has_premium_access()})


@harvestiq_bp.route("/save-wallet", methods=["POST"])
def save_wallet():
    data = payload_from_request()
    address = normalize_wallet(data.get("address"))
    chain = (data.get("chain") or "eth").strip().lower()
    if not validate_wallet(address):
        return jsonify({"error": "Enter a valid wallet address."}), 400
    if chain not in SUPPORTED_CHAINS:
        return jsonify({"error": "Unsupported chain selected."}), 400
    save_wallet_to_session(address, chain)
    return jsonify({"ok": True, "saved_wallets": session_list("saved_wallets")})


@harvestiq_bp.route("/history")
def history():
    return jsonify(
        {
            "saved_wallets": session_list("saved_wallets"),
            "scan_history": session_list("scan_history"),
            "authenticated_wallet": current_authenticated_wallet(),
            "premium_access": has_premium_access(),
            "is_premium": has_premium_access(),
        }
    )


@harvestiq_bp.route("/share-score", methods=["POST"])
def share_score():
    data = payload_from_request()
    report = selected_report((data.get("report_id") or "").strip())
    if not report:
        return jsonify({"error": "Report not found."}), 404

    share_text = share_text_for_report(report)
    tweet_url = f"https://twitter.com/intent/tweet?text={quote(share_text)}"
    return jsonify({"text": share_text, "tweet_url": tweet_url, "card_text": f"{report['chain_label']} | {report['score']}/100 | {report['risk_level']} risk"})


@harvestiq_bp.route("/leaderboard")
def leaderboard():
    return jsonify({"leaders": leaderboard_rows()[:10]})


@harvestiq_bp.route("/report/<report_id>")
def view_report(report_id: str):
    report = get_report(report_id)
    if not report:
        return redirect(url_for("harvestiq.index"))
    if not has_premium_access():
        return redirect(url_for("harvestiq.payment", report_id=report_id))
    return render_template("report.html", report=report, payment_amount=str(PAYMENT_AMOUNT_USDT), authenticated_wallet=current_authenticated_wallet())


@harvestiq_bp.route("/api/report/<report_id>")
def api_report(report_id: str):
    report = get_report(report_id)
    if not report:
        return jsonify({"error": "Report not found."}), 404
    if not has_premium_access():
        return jsonify({"error": "Premium report locked."}), 403
    return jsonify(report)


__all__ = [
    "harvestiq_bp",
    "analyze",
    "auth_nonce",
    "auth_verify",
    "check_payment",
    "health",
    "history",
    "index",
    "leaderboard",
    "payment",
    "payment_status_route",
    "save_wallet",
    "session_state",
    "share_score",
    "view_report",
    "api_report",
]
