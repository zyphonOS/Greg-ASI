from __future__ import annotations

from flask import Blueprint, current_app, jsonify, render_template, request

from greg_local_memory import get_local_memory
from zyphonos.billing import Billing
from zyphonos.enterprise import ZyphonOS


zyphonos_bp = Blueprint("zyphonos", __name__)
memory = get_local_memory()
zyphonos_service = ZyphonOS(memory)
billing_service = Billing(memory)


@zyphonos_bp.route("/")
def landing():
    greg = current_app.extensions.get("greg")
    preview = greg.think("Summarize ZyphonOS for a founder landing page.", mode="founder") if greg else "Greg core is offline."
    clients = zyphonos_service.list_clients()
    invoices = billing_service.recent_invoices(limit=8)
    return render_template("zyphonos.html", greg_preview=preview, clients=clients[:6], invoices=invoices[:6])


@zyphonos_bp.route("/api/clients", methods=["GET"])
def list_clients():
    return jsonify({"ok": True, "clients": zyphonos_service.list_clients()})


@zyphonos_bp.route("/api/clients", methods=["POST"])
def register_client():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip()
    tier = (payload.get("tier") or "free").strip()
    if not name or not email:
        return jsonify({"error": "name and email are required"}), 400
    client = zyphonos_service.register_client(name, email, tier)
    return jsonify({"ok": True, "client": client.dict()})


@zyphonos_bp.route("/api/invoices", methods=["GET"])
def list_invoices():
    return jsonify({"ok": True, "invoices": billing_service.recent_invoices()})


@zyphonos_bp.route("/api/invoices", methods=["POST"])
def create_invoice():
    payload = request.get_json(silent=True) or {}
    client_id = (payload.get("client_id") or "").strip()
    tier = (payload.get("tier") or "free").strip()
    usage = int(payload.get("usage", 0) or 0)
    if not client_id:
        return jsonify({"error": "client_id required"}), 400
    invoice = billing_service.generate_invoice(client_id, tier, usage)
    return jsonify({"ok": True, "invoice": invoice})
