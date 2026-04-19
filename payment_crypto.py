from __future__ import annotations

import hashlib
import os
import time

from flask import jsonify, request


DEFAULT_NETWORK = "ERC-20"
DEFAULT_CURRENCY = "USDT"
DEFAULT_AMOUNT_USDT = 49.0
PRODUCT_PRICES = {
    "personal": 49.0,
    "creative-coach": 149.0,
    "enterprise": 499.0,
}


def _receiver_wallet_address() -> str:
    return (os.getenv("RECEIVER_WALLET_ADDRESS") or os.getenv("GREG_WALLET_ADDRESS") or "").strip()


def _requested_product(data: dict) -> str:
    raw = str(data.get("product_id") or data.get("tier") or "personal").strip().lower()
    aliases = {
        "creative_coach": "creative-coach",
        "coach": "creative-coach",
        "starter": "personal",
        "pro": "creative-coach",
        "team": "enterprise",
    }
    return aliases.get(raw, raw)


def _allowed_amount(data: dict, product_id: str) -> float:
    if product_id in PRODUCT_PRICES:
        return PRODUCT_PRICES[product_id]
    try:
        requested = float(data.get("amount", DEFAULT_AMOUNT_USDT) or DEFAULT_AMOUNT_USDT)
    except Exception:
        requested = DEFAULT_AMOUNT_USDT
    rounded = round(requested, 2)
    return rounded if rounded in {49.0, 149.0, 499.0} else DEFAULT_AMOUNT_USDT


def build_checkout_payload(data: dict | None = None) -> dict:
    body = data or {}
    wallet_address = _receiver_wallet_address()
    if not wallet_address:
        raise ValueError("RECEIVER_WALLET_ADDRESS is not configured.")
    product_id = _requested_product(body)
    amount_usdt = _allowed_amount(body, product_id)
    customer_email = str(body.get("email") or "").strip().lower()
    nonce = f"{wallet_address}|{product_id}|{amount_usdt:.2f}|{customer_email}|{int(time.time())}"
    payment_id = hashlib.sha256(nonce.encode("utf-8")).hexdigest()[:16]
    return {
        "ok": True,
        "payment_id": payment_id,
        "product_id": product_id,
        "currency": DEFAULT_CURRENCY,
        "network": DEFAULT_NETWORK,
        "amount_usdt": amount_usdt,
        "amount_display": f"{amount_usdt:.2f} {DEFAULT_CURRENCY}",
        "address": wallet_address,
        "instructions": f"Send exactly {amount_usdt:.2f} {DEFAULT_CURRENCY} on {DEFAULT_NETWORK} to the address below.",
        "status": "pending",
        "verification": "manual",
        "expires_at": int(time.time()) + 3600,
    }


def crypto_checkout():
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(build_checkout_payload(data))
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 503


def crypto_verify():
    data = request.get_json(silent=True) or {}
    return jsonify(
        {
            "ok": True,
            "payment_id": str(data.get("payment_id") or "").strip(),
            "tx_hash": str(data.get("tx_hash") or "").strip(),
            "verified": False,
            "status": "manual_review_required",
            "message": "Manual verification helper is still available as a fallback rail.",
        }
    )
