from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from flask import Blueprint, jsonify, request

from core.utils import data_path, read_json, write_json
from greg_identity import issue_access_token


payment_bp = Blueprint("payment", __name__)

BASE_RPC = os.getenv("BASE_RPC_URL", "https://mainnet.base.org")
TREASURY_WALLET = os.getenv("GREG_WALLET_ADDRESS", os.getenv("RECEIVER_WALLET_ADDRESS", "0x6ccE7bdeeF12E499e2A834734da0A21135fc29aD"))
USDC_CONTRACT = os.getenv("BASE_USDC_CONTRACT", "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913")
ETH_PRICE_USD = float(os.getenv("ETH_PRICE_USD", "3200"))
PAYMENT_LOG = data_path("greg_payments.jsonl")
ACTIVATIONS_PATH = data_path("greg_payment_activations.json")

PRODUCTS = {
    "predict_monthly": {"name": "Greg Prediction Feed", "price_usd": 9.0, "access_tier": "explorer"},
    "builder_sprint": {"name": "Builder Sprint", "price_usd": 39.0, "access_tier": "pikkaio_client"},
    "studio_sprint": {"name": "Studio Sprint", "price_usd": 149.0, "access_tier": "zyphonos_client"},
    "launch_pack": {"name": "Launch Pack", "price_usd": 99.0, "access_tier": "pikkaio_client"},
}


def _load_payments() -> list[dict]:
    if not PAYMENT_LOG.exists():
        return []
    rows = []
    for line in PAYMENT_LOG.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def _save_payment(record: dict) -> None:
    PAYMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with PAYMENT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def _load_payment(payment_id: str) -> dict | None:
    latest = None
    for record in _load_payments():
        if record.get("payment_id") == payment_id:
            latest = record
    return latest


def _save_activation(payment_id: str, payload: dict) -> None:
    data = read_json(ACTIVATIONS_PATH, {"activations": {}})
    data.setdefault("activations", {})[payment_id] = payload
    write_json(ACTIVATIONS_PATH, data)


def _rpc_call(method: str, params: list) -> dict:
    response = requests.post(
        BASE_RPC,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get("result") or {}


def _eth_amount(usd: float) -> float:
    return round(usd / ETH_PRICE_USD, 6)


def _usdc_raw(usd: float) -> int:
    return int(round(usd * 1_000_000))


def _verify_eth_tx(tx_hash: str, expected_to: str, min_eth: float, expected_from: str = "") -> dict:
    try:
        receipt = _rpc_call("eth_getTransactionReceipt", [tx_hash])
        if not receipt:
            return {"ok": False, "confirmed": False, "error": "tx not found or pending"}
        if int(receipt.get("status", "0x0"), 16) != 1:
            return {"ok": False, "confirmed": False, "error": "tx failed on-chain"}
        tx = _rpc_call("eth_getTransactionByHash", [tx_hash])
        if not tx:
            return {"ok": False, "confirmed": False, "error": "tx lookup failed"}
        to_addr = (tx.get("to") or "").lower()
        from_addr = (tx.get("from") or "").lower()
        if to_addr != expected_to.lower():
            return {"ok": False, "confirmed": False, "error": f"wrong recipient: {to_addr}"}
        if expected_from and from_addr != expected_from.lower():
            return {"ok": False, "confirmed": False, "error": f"wrong sender: {from_addr}"}
        value_eth = int(tx.get("value", "0x0"), 16) / 1e18
        if value_eth < min_eth * 0.95:
            return {"ok": False, "confirmed": False, "error": f"insufficient amount: {value_eth:.6f} ETH"}
        return {"ok": True, "confirmed": True, "value_eth": value_eth, "from": from_addr}
    except Exception as exc:
        return {"ok": False, "confirmed": False, "error": str(exc)}


def _verify_usdc_tx(tx_hash: str, expected_to: str, min_usdc: float, expected_from: str = "") -> dict:
    transfer_topic = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    try:
        receipt = _rpc_call("eth_getTransactionReceipt", [tx_hash])
        if not receipt:
            return {"ok": False, "confirmed": False, "error": "tx not found or pending"}
        if int(receipt.get("status", "0x0"), 16) != 1:
            return {"ok": False, "confirmed": False, "error": "tx failed on-chain"}
        for log in receipt.get("logs", []):
            if (log.get("address") or "").lower() != USDC_CONTRACT.lower():
                continue
            topics = log.get("topics", [])
            if len(topics) < 3 or topics[0].lower() != transfer_topic:
                continue
            from_addr = "0x" + topics[1][-40:]
            to_addr = "0x" + topics[2][-40:]
            if expected_from and from_addr.lower() != expected_from.lower():
                continue
            if to_addr.lower() != expected_to.lower():
                continue
            amount_usdc = int(log.get("data", "0x0"), 16) / 1_000_000
            if amount_usdc < min_usdc * 0.95:
                return {"ok": False, "confirmed": False, "error": f"insufficient amount: {amount_usdc:.2f} USDC"}
            return {"ok": True, "confirmed": True, "value_usdc": amount_usdc, "from": from_addr}
        return {"ok": False, "confirmed": False, "error": "no matching USDC transfer found"}
    except Exception as exc:
        return {"ok": False, "confirmed": False, "error": str(exc)}


def _access_tier_for_product(product_id: str) -> str:
    return PRODUCTS.get(product_id, {}).get("access_tier", "explorer")


@payment_bp.route("/api/payment/products", methods=["GET"])
def api_payment_products():
    products = []
    for product_id, payload in PRODUCTS.items():
        products.append(
            {
                "id": product_id,
                **payload,
                "price_eth": _eth_amount(payload["price_usd"]),
                "price_usdc": round(payload["price_usd"], 2),
                "usdc_raw": _usdc_raw(payload["price_usd"]),
                "treasury": TREASURY_WALLET,
                "network": "Base Mainnet",
                "chain_id": 8453,
            }
        )
    return jsonify({"ok": True, "products": products, "treasury": TREASURY_WALLET, "usdc_contract": USDC_CONTRACT})


@payment_bp.route("/api/payment/intent", methods=["POST"])
def api_payment_intent():
    data = request.get_json(silent=True) or {}
    product_id = str(data.get("product_id") or "predict_monthly").strip()
    currency = str(data.get("currency") or "usdc").strip().lower()
    wallet = str(data.get("wallet") or "").strip().lower()
    project_id = str(data.get("project_id") or "").strip()
    product = PRODUCTS.get(product_id)
    if not product:
        return jsonify({"ok": False, "error": "Unknown product."}), 400
    if currency not in {"eth", "usdc"}:
        return jsonify({"ok": False, "error": "Currency must be 'eth' or 'usdc'."}), 400

    payment_id = "pay_" + secrets.token_hex(12)
    record = {
        "payment_id": payment_id,
        "product_id": product_id,
        "currency": currency,
        "buyer_wallet": wallet,
        "project_id": project_id,
        "amount_usd": product["price_usd"],
        "amount_eth": _eth_amount(product["price_usd"]),
        "amount_usdc": round(product["price_usd"], 2),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
    }
    _save_payment(record)
    return jsonify(
        {
            "ok": True,
            "payment_id": payment_id,
            "product_id": product_id,
            "currency": currency,
            "send_to": TREASURY_WALLET,
            "network": "Base Mainnet",
            "chain_id": 8453,
            "amount": {
                "usd": product["price_usd"],
                "eth": record["amount_eth"],
                "usdc": record["amount_usdc"],
                "usdc_raw": _usdc_raw(product["price_usd"]),
            },
            "usdc_contract": USDC_CONTRACT,
            "status_url": f"/api/payment/status/{payment_id}",
        }
    )


@payment_bp.route("/api/payment/verify", methods=["POST"])
def api_payment_verify():
    data = request.get_json(silent=True) or {}
    payment_id = str(data.get("payment_id") or "").strip()
    tx_hash = str(data.get("tx_hash") or "").strip()
    if not payment_id or not tx_hash:
        return jsonify({"ok": False, "error": "payment_id and tx_hash required"}), 400
    intent = _load_payment(payment_id)
    if not intent:
        return jsonify({"ok": False, "error": "payment intent not found"}), 404
    if intent.get("status") == "confirmed":
        return jsonify({"ok": True, "already_confirmed": True, **intent})

    expected_wallet = intent.get("buyer_wallet", "")
    amount_usd = float(intent.get("amount_usd", 0.0))
    if intent.get("currency") == "eth":
        verification = _verify_eth_tx(tx_hash, TREASURY_WALLET, _eth_amount(amount_usd), expected_from=expected_wallet)
    else:
        verification = _verify_usdc_tx(tx_hash, TREASURY_WALLET, amount_usd, expected_from=expected_wallet)
    if not verification.get("ok"):
        return jsonify({"ok": False, "status": "failed", "error": verification.get("error")}), 400

    access_token = issue_access_token(
        tier_name=_access_tier_for_product(intent["product_id"]),
        label=PRODUCTS[intent["product_id"]]["name"],
        metadata={
            "payment_id": payment_id,
            "product_id": intent["product_id"],
            "buyer_wallet": expected_wallet,
            "tx_hash": tx_hash,
            "source": "base_checkout",
        },
    )
    activation = {
        **intent,
        "status": "confirmed",
        "tx_hash": tx_hash,
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
        "access_token": access_token,
        "verification": verification,
    }
    _save_payment(activation)
    _save_activation(payment_id, activation)
    return jsonify({"ok": True, "status": "confirmed", "access_token": access_token, "verification": verification, "payment": activation})


@payment_bp.route("/api/payment/status/<payment_id>", methods=["GET"])
def api_payment_status(payment_id: str):
    intent = _load_payment(payment_id)
    if not intent:
        return jsonify({"ok": False, "error": "payment not found"}), 404
    return jsonify({"ok": True, "payment": intent})
