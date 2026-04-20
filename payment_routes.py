from __future__ import annotations

import json
import os
from typing import Any

import requests
from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from constitution_runtime import constitutional_revenue_allocation
from user_auth import (
    BASE_SEPOLIA_CHAIN_ID,
    attach_wallet,
    confirm_payment,
    create_payment_record,
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


def _human_usdc(raw_hex: str) -> float:
    return round(int(str(raw_hex or "0x0"), 16) / (10 ** USDC_DECIMALS), 6)


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


def _verify_usdc_transfer(tx_hash: str, *, expected_to: str, expected_amount_usdc: float, expected_from: str = "") -> dict[str, Any]:
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


@payment_api_bp.route("/api/wallet/balance", methods=["POST"])
@login_required
def api_wallet_balance():
    payload = request.get_json(silent=True) or {}
    wallet_address = str(payload.get("wallet_address") or current_user.wallet_address or "").strip()
    if not wallet_address:
        return jsonify({"ok": False, "error": "wallet_address is required"}), 400
    try:
        if wallet_address != current_user.wallet_address:
            attach_wallet(current_user.id, wallet_address)
        return jsonify({"ok": True, **_wallet_balance(wallet_address)})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Unable to fetch wallet balance: {exc}"}), 500


@payment_api_bp.route("/api/payment/create-intent", methods=["POST"])
@login_required
def api_create_payment_intent():
    payload = request.get_json(silent=True) or {}
    amount_usdc = round(float(payload.get("amount_usdc") or 0.0), 6)
    service = str(payload.get("service") or "intent").strip().lower() or "intent"
    if amount_usdc <= 0:
        return jsonify({"ok": False, "error": "amount_usdc must be greater than zero"}), 400

    wallet_address = str(payload.get("wallet_address") or current_user.wallet_address or "").strip()
    split = constitutional_revenue_allocation(amount_usdc)
    payment_id = create_payment_record(
        user_id=current_user.id,
        amount_usdc=amount_usdc,
        service=service,
        wallet_address=wallet_address or None,
        chain_id=BASE_CHAIN_ID,
        network=BASE_NETWORK_NAME,
        raw_request=payload,
        split=split,
        metadata={"creator_email": current_user.email},
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
            "amount_raw": int(amount_usdc * (10 ** USDC_DECIMALS)),
            "service": service,
            "split": split,
            "transaction_request": {
                "to": BASE_USDC_CONTRACT,
                "method": "transfer",
                "args": [TREASURY_WALLET, int(amount_usdc * (10 ** USDC_DECIMALS))],
            },
        }
    )


@payment_api_bp.route("/api/payment/confirm", methods=["POST"])
@login_required
def api_confirm_payment():
    payload = request.get_json(silent=True) or {}
    payment_id = str(payload.get("payment_id") or "").strip()
    tx_hash = str(payload.get("tx_hash") or "").strip()
    if not payment_id or not tx_hash:
        return jsonify({"ok": False, "error": "payment_id and tx_hash are required"}), 400

    payment = get_payment(payment_id)
    if not payment or str(payment.get("user_id")) != str(current_user.id):
        return jsonify({"ok": False, "error": "payment not found"}), 404

    try:
        verification = _verify_usdc_transfer(
            tx_hash,
            expected_to=TREASURY_WALLET,
            expected_amount_usdc=float(payment.get("amount_usdc") or 0.0),
            expected_from=str(payment.get("wallet_address") or current_user.wallet_address or "").strip(),
        )
        if not verification.get("ok"):
            return jsonify({"ok": False, "error": verification.get("error")}), 400
        confirmed = confirm_payment(payment_id, tx_hash, metadata={"verification": verification})
        service = str(payment.get("service") or "intent")
        if service == "subscription":
            set_user_premium(current_user.id, duration_days=30)
        return jsonify(
            {
                "ok": True,
                "payment": confirmed,
                "verification": verification,
                "service_ready": True,
                "credit_message": f"{service} payment confirmed on {BASE_NETWORK_NAME}.",
            }
        )
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Payment confirmation failed: {exc}"}), 500


@payment_api_bp.route("/api/payment/summary", methods=["GET"])
@login_required
def api_payment_summary():
    summary = payment_summary_for_user(current_user.id)
    summary["split"] = constitutional_revenue_allocation(summary.get("confirmed_usdc") or 0.0)
    return jsonify({"ok": True, **summary})
