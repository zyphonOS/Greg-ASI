from __future__ import annotations

import os
import secrets
import sys
from typing import Any

import requests
from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user

from constitution_guard import ConstitutionViolation, validate_intent_against_constitution
from constitution_runtime import constitutional_revenue_allocation
from user_auth import (
    BASE_SEPOLIA_CHAIN_ID,
    attach_wallet,
    confirm_payment,
    create_payment_record,
    get_or_create_public_checkout_user,
    get_payment,
    payment_summary_for_user,
    set_user_premium,
)


payment_api_bp = Blueprint("payment_api", __name__)
BASE_RPC_URL = os.getenv("BASE_RPC_URL", "https://sepolia.base.org")
BASE_CHAIN_ID = int(os.getenv("BASE_CHAIN_ID", str(BASE_SEPOLIA_CHAIN_ID)))
BASE_NETWORK_NAME = os.getenv("BASE_NETWORK_NAME", "Base Sepolia")
BASE_USDC_CONTRACT = os.getenv(
    "BASE_USDC_CONTRACT",
    "0x036CbD53842c5426634e7929541eC2318f3dCf7e",
)
TREASURY_WALLET = os.getenv(
    "GREG_WALLET_ADDRESS",
    os.getenv("RECEIVER_WALLET_ADDRESS", "0x000000000000000000000000000000000000dEaD"),
)
USDC_DECIMALS = 6
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
# SECURITY: No hardcoded fallback. Set PUBLIC_PAYMENT_API_KEY in Railway env vars.
# If unset, _api_key_valid() returns False and mock_confirm is permanently disabled.
PUBLIC_PAYMENT_API_KEY = os.getenv("PUBLIC_PAYMENT_API_KEY", "")
SERVICE_PRICES = {
    "image": 5.0,
    "code": 10.0,
    "intent": 10.0,
    "task": 2.0,
    "subscription": 5.0,
}


def _rpc_call(method: str, params: list[Any]) -> Any:
    response = requests.post(
        BASE_RPC_URL,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise RuntimeError(payload["error"])
    return payload.get("result")


def _encode_balance_of(wallet_address: str) -> str:
    address = str(wallet_address or "").strip().lower().replace("0x", "")
    padded = address.rjust(64, "0")
    return "0x70a08231" + padded


def _encode_transfer(recipient: str, amount_raw: int) -> str:
    recipient_clean = str(recipient or "").strip().lower().replace("0x", "").rjust(64, "0")
    amount_clean = hex(int(amount_raw))[2:].rjust(64, "0")
    return "0xa9059cbb" + recipient_clean + amount_clean


def _human_usdc(raw_hex: str) -> float:
    return round(int(str(raw_hex or "0x0"), 16) / (10 ** USDC_DECIMALS), 6)


def _price_for_service(service: str) -> float:
    clean = str(service or "task").strip().lower() or "task"
    return float(SERVICE_PRICES.get(clean, 5.0))


def _api_key_valid() -> bool:
    provided = str(request.headers.get("X-Greg-API-Key") or "").strip()
    return bool(provided and PUBLIC_PAYMENT_API_KEY and secrets.compare_digest(provided, PUBLIC_PAYMENT_API_KEY))


def _request_user_context() -> tuple[Any, bool]:
    if getattr(current_user, "is_authenticated", False):
        return current_user, True
    return get_or_create_public_checkout_user(), False


def _host_base_url() -> str:
    return request.host_url.rstrip("/")


def _wallet_balance(wallet_address: str) -> dict[str, Any]:
    result = _rpc_call(
        "eth_call",
        [
            {"to": BASE_USDC_CONTRACT, "data": _encode_balance_of(wallet_address)},
            "latest",
        ],
    )
    return {
        "wallet_address": wallet_address,
        "contract": BASE_USDC_CONTRACT,
        "network": BASE_NETWORK_NAME,
        "chain_id": BASE_CHAIN_ID,
        "balance_usdc": _human_usdc(result),
        "raw_balance": result,
    }


def _verify_usdc_transfer(
    tx_hash: str,
    *,
    expected_to: str,
    expected_amount_usdc: float,
    expected_from: str = "",
) -> dict[str, Any]:
    receipt = _rpc_call("eth_getTransactionReceipt", [tx_hash])
    if not receipt:
        return {"ok": False, "error": "transaction not found or still pending"}
    if int(receipt.get("status", "0x0"), 16) != 1:
        return {"ok": False, "error": "transaction reverted"}
    for log in receipt.get("logs", []):
        if (log.get("address") or "").lower() != BASE_USDC_CONTRACT.lower():
            continue
        topics = [str(item).lower() for item in log.get("topics", [])]
        if len(topics) < 3 or topics[0] != TRANSFER_TOPIC:
            continue
        from_address = "0x" + topics[1][-40:]
        to_address = "0x" + topics[2][-40:]
        amount_usdc = int(log.get("data", "0x0"), 16) / (10 ** USDC_DECIMALS)
        if expected_from and from_address.lower() != expected_from.lower():
            continue
        if to_address.lower() != expected_to.lower():
            continue
        if amount_usdc + 1e-9 < expected_amount_usdc:
            return {"ok": False, "error": f"insufficient amount {amount_usdc:.6f} USDC"}
        return {
            "ok": True,
            "from": from_address,
            "to": to_address,
            "amount_usdc": round(amount_usdc, 6),
            "receipt": receipt,
        }
    return {"ok": False, "error": "matching USDC transfer not found in receipt"}


def _service_prompt(payment: dict[str, Any]) -> str:
    raw_request = payment.get("raw_request") or {}
    return str(
        raw_request.get("description")
        or raw_request.get("prompt")
        or raw_request.get("task")
        or raw_request.get("intent")
        or ""
    ).strip()


def _execute_paid_service(payment: dict[str, Any], verification: dict[str, Any]) -> dict[str, Any]:
    service = str(payment.get("service") or "task").strip().lower()
    prompt = _service_prompt(payment)
    if not prompt and service != "subscription":
        raise RuntimeError("No prompt or description was supplied for the paid service.")

    payload = {
        "description": prompt,
        "prompt": prompt,
        "task": prompt,
        "endpoint": "/api/payment/confirm",
        "payment_id": payment.get("payment_id"),
        "wallet_address": payment.get("wallet_address"),
        "base_url": _host_base_url(),
        "revenue_generated": float(payment.get("amount_usdc") or 0.0),
        "build_protocol_steps": ["1", "2", "3", "4", "5", "6", "7"],
    }
    validate_intent_against_constitution(f"paid service {service}: {prompt}", payload)

    if service == "image":
        from image_generator import generate_image_asset

        image_result = generate_image_asset(prompt, base_url=_host_base_url())
        return {
            "service": "image",
            "status": "done",
            "image_url": image_result["image_url"],
            "provider": image_result["provider"],
        }

    if service in {"code", "intent"}:
        main_mod = sys.modules.get("main") or sys.modules.get("__main__")
        process_intent = getattr(main_mod, "process_intent", None)
        if process_intent is None:
            from main import process_intent as process_intent  # type: ignore

        result = process_intent(
            str(payment.get("payment_id") or f"intent_{secrets.token_hex(4)}"),
            prompt,
            payload,
        )
        return {"service": "code", **result}

    if service == "subscription":
        return {
            "service": "subscription",
            "status": "done",
            "message": "Premium access activated.",
        }

    command_locus = current_app.extensions.get("command_locus")
    if command_locus is None:
        raise RuntimeError("Greg command locus is unavailable.")
    body, status_code = command_locus.dispatch(
        "think",
        {
            "prompt": prompt,
            "mode": "studio",
            "user_id": f"payment-{payment.get('payment_id')}",
        },
    )
    if status_code >= 400 or not body.get("ok"):
        raise RuntimeError(body.get("error") or "Greg did not complete the paid task.")
    return {
        "service": "task",
        "status": "done",
        "response": body.get("response"),
        "tick": body.get("tick"),
    }


@payment_api_bp.route("/api/wallet/balance", methods=["POST"])
def api_wallet_balance():
    payload = request.get_json(silent=True) or {}
    wallet_address = str(payload.get("wallet_address") or getattr(current_user, "wallet_address", "") or "").strip()
    if not wallet_address:
        return jsonify({"ok": False, "error": "wallet_address is required"}), 400
    try:
        if getattr(current_user, "is_authenticated", False) and wallet_address != current_user.wallet_address:
            attach_wallet(current_user.id, wallet_address)
        return jsonify({"ok": True, **_wallet_balance(wallet_address)})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Unable to fetch wallet balance: {exc}"}), 500


@payment_api_bp.route("/api/payment/create-intent", methods=["POST"])
def api_create_payment_intent():
    payload = request.get_json(silent=True) or {}
    service = str(payload.get("service") or "intent").strip().lower() or "intent"
    description = str(
        payload.get("description")
        or payload.get("prompt")
        or payload.get("task")
        or payload.get("intent")
        or ""
    ).strip()
    amount_usdc = round(_price_for_service(service), 6)
    if not description and service != "subscription":
        return jsonify({"ok": False, "error": "description is required"}), 400

    actor, authenticated = _request_user_context()
    wallet_address = str(payload.get("wallet_address") or getattr(actor, "wallet_address", "") or "").strip()
    split = constitutional_revenue_allocation(amount_usdc)
    amount_raw = int(amount_usdc * (10 ** USDC_DECIMALS))
    payment_id = create_payment_record(
        user_id=actor.id,
        amount_usdc=amount_usdc,
        service=service,
        wallet_address=wallet_address or None,
        chain_id=BASE_CHAIN_ID,
        network=BASE_NETWORK_NAME,
        raw_request={**payload, "description": description, "service": service},
        split=split,
        metadata={
            "creator_email": getattr(actor, "email", "public-checkout@gregasi.local"),
            "authenticated": authenticated,
            "api_key_mode": _api_key_valid(),
        },
    )
    return jsonify(
        {
            "ok": True,
            "payment_id": payment_id,
            "network": BASE_NETWORK_NAME,
            "chain_id": BASE_CHAIN_ID,
            "currency": "USDC",
            "treasury_wallet": TREASURY_WALLET,
            "usdc_contract": BASE_USDC_CONTRACT,
            "amount_usdc": amount_usdc,
            "amount_raw": amount_raw,
            "service": service,
            "description": description,
            "split": split,
            "api_key_mode": _api_key_valid(),
            "transaction_request": {
                "to": BASE_USDC_CONTRACT,
                "from": wallet_address or None,
                "value": hex(0),
                "data": _encode_transfer(TREASURY_WALLET, amount_raw),
                "chainId": hex(BASE_CHAIN_ID),
            },
        }
    )


@payment_api_bp.route("/api/payment/confirm", methods=["POST"])
def api_confirm_payment():
    payload = request.get_json(silent=True) or {}
    payment_id = str(payload.get("payment_id") or "").strip()
    tx_hash = str(payload.get("tx_hash") or "").strip()
    if not payment_id or not tx_hash:
        return jsonify({"ok": False, "error": "payment_id and tx_hash are required"}), 400

    payment = get_payment(payment_id)
    if not payment:
        return jsonify({"ok": False, "error": "payment not found"}), 404

    try:
        # SECURITY: mock_confirm removed. Every payment requires a real on-chain tx_hash.
        verification = _verify_usdc_transfer(
            tx_hash,
            expected_to=TREASURY_WALLET,
            expected_amount_usdc=float(payment.get("amount_usdc") or 0.0),
            expected_from=str(payload.get("wallet_address") or payment.get("wallet_address") or "").strip(),
        )
        if not verification.get("ok"):
            return jsonify({"ok": False, "error": verification.get("error")}), 400
        confirmed = confirm_payment(payment_id, tx_hash, metadata={"verification": verification})
        if str(payment.get("service") or "") == "subscription":
            set_user_premium(payment["user_id"], duration_days=30)
        service_result = _execute_paid_service(confirmed, verification)
        return jsonify(
            {
                "ok": True,
                "payment": confirmed,
                "verification": verification,
                "service_ready": True,
                "service_result": service_result,
                "credit_message": f"{payment.get('service', 'payment')} confirmed on {BASE_NETWORK_NAME}.",
            }
        )
    except ConstitutionViolation as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Payment confirmation failed: {exc}"}), 500


@payment_api_bp.route("/api/payment/summary", methods=["GET"])
def api_payment_summary():
    if getattr(current_user, "is_authenticated", False):
        summary = payment_summary_for_user(current_user.id)
    else:
        summary = {"confirmed_usdc": 0.0, "pending_usdc": 0.0, "payments": []}
    summary["split"] = constitutional_revenue_allocation(summary.get("confirmed_usdc") or 0.0)
    return jsonify({"ok": True, **summary})
