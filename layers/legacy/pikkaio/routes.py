from __future__ import annotations

import uuid

from flask import Blueprint, current_app, jsonify, render_template, request, session, url_for

from greg_local_memory import get_local_memory
from greg_pikkaio import _get_engine as get_project_engine
from greg_tending import TendingEngine
from pikkaio.revenue import RevenueTracker


pikkaio_bp = Blueprint("pikkaio", __name__)
memory = get_local_memory()
revenue_tracker = RevenueTracker(memory)
tending_engine = TendingEngine()


def _greg():
    return current_app.extensions.get("greg")


def _builder_id(create: bool = True, payload: dict | None = None) -> str:
    payload = payload or {}
    requested = (
        payload.get("builder_id")
        or payload.get("user_id")
        or request.args.get("builder_id")
        or request.headers.get("X-Builder-Id")
        or session.get("pikkaio_builder_id")
    )
    resolved = str(requested).strip() if requested else ""
    if not resolved and create:
        resolved = f"builder-{uuid.uuid4().hex[:10]}"
    if resolved:
        session["pikkaio_builder_id"] = resolved
    return resolved


def _builder_intents(builder_id: str) -> list:
    if not builder_id:
        return []
    intents = [intent for intent in get_project_engine().list_intents() if intent.builder_id == builder_id]
    return intents


def _latest_intent(builder_id: str):
    intents = _builder_intents(builder_id)
    if not intents:
        return None
    latest_id = session.get("pikkaio_latest_intent_id")
    if latest_id:
        for intent in intents:
            if intent.id == latest_id:
                return intent
    return intents[0]


def _active_intervention(intent) -> dict | None:
    if not intent:
        return None
    interventions = intent.interventions
    if not interventions:
        return None
    return interventions[-1]


def _surface_status(builder_id: str) -> dict:
    intent = _latest_intent(builder_id)
    summary = get_project_engine().summary()
    intervention = _active_intervention(intent)
    if not intent:
        return {
            "builder_id": builder_id,
            "has_intent": False,
            "intent": None,
            "drift_score": None,
            "status": "undeclared",
            "intervention": None,
            "acknowledgement": session.get("pikkaio_last_ack", ""),
            "builder_intent_count": 0,
            "field_summary": summary,
        }
    return {
        "builder_id": builder_id,
        "has_intent": True,
        "intent": intent.to_dict(),
        "drift_score": round(float(intent.drift_score or 0.0), 4),
        "status": intent.status,
        "intervention": intervention,
        "acknowledgement": session.get("pikkaio_last_ack", ""),
        "builder_intent_count": len(_builder_intents(builder_id)),
        "field_summary": summary,
    }


@pikkaio_bp.route("/", strict_slashes=False)
def board():
    builder_id = _builder_id(create=True)
    builder_state = _surface_status(builder_id)
    return render_template(
        "pikkaio.html",
        builder_state=builder_state,
        logo_url=url_for("static", filename="images/pikkaio_logo.png"),
    )


@pikkaio_bp.route("/intent", methods=["POST"])
def declare_intent():
    payload = request.get_json(silent=True) or {}
    description = (payload.get("description") or "").strip()
    deadline = (payload.get("deadline") or "").strip()
    revenue_target = float(payload.get("revenue_target", 0) or 0)
    if not description:
        return jsonify({"error": "Intent description required."}), 400

    builder_id = _builder_id(create=True, payload=payload)
    intent = get_project_engine().declare_intent(
        builder_id=builder_id,
        description=description,
        deadline=deadline,
        revenue_target=revenue_target,
        referral_source="pikkaio-surface",
    )
    session["pikkaio_latest_intent_id"] = intent.id
    greg = _greg()
    if greg:
        acknowledgement = greg.voice.acknowledge_intent(
            builder_id=builder_id,
            intent=description,
            deadline=deadline,
            revenue_target=revenue_target,
            snapshot=greg.status_snapshot(),
        )
    else:
        acknowledgement = "Intent received. The line is now being tracked."
    lowered_ack = acknowledgement.lower()
    if "intent received" not in lowered_ack and "tracked" not in lowered_ack:
        acknowledgement = f"{acknowledgement} The line is now being tracked."
    session["pikkaio_last_ack"] = acknowledgement
    return jsonify(
        {
            "ok": True,
            "builder_id": builder_id,
            "intent": intent.to_dict(),
            "acknowledgement": acknowledgement,
            "status": _surface_status(builder_id),
        }
    )


@pikkaio_bp.route("/status", methods=["GET"])
def status():
    builder_id = _builder_id(create=True)
    return jsonify({"ok": True, **_surface_status(builder_id)})


@pikkaio_bp.route("/api/intents", methods=["GET"])
def intents_api():
    engine = get_project_engine()
    builder_id = _builder_id(create=True)
    return jsonify(
        {
            "projects": {project_id: project.to_dict() for project_id, project in engine.projects.items()},
            "summary": engine.summary(),
            "builder_status": _surface_status(builder_id),
        }
    )


@pikkaio_bp.route("/api/intents", methods=["POST"])
def declare_intent_legacy():
    return declare_intent()


@pikkaio_bp.route("/api/intents/<intent_id>/progress", methods=["POST"])
def update_progress(intent_id: str):
    payload = request.get_json(silent=True) or {}
    progress = float(payload.get("progress", 0) or 0)
    updated = get_project_engine().update_progress(intent_id, progress, status=payload.get("status"))
    if updated is None:
        return jsonify({"error": "Intent not found."}), 404
    return jsonify({"ok": True, "intent": updated.to_dict()})


@pikkaio_bp.route("/api/intents/<intent_id>/revenue", methods=["POST"])
def add_revenue(intent_id: str):
    payload = request.get_json(silent=True) or {}
    amount = float(payload.get("amount", 0) or 0)
    source = (payload.get("source") or "manual").strip()
    project = get_project_engine().get_intent(intent_id)
    if not project:
        return jsonify({"error": "Intent not found."}), 404
    revenue_tracker.add_earning(project.creator, amount, source)
    updated = get_project_engine().record_revenue(intent_id, amount, source)
    return jsonify(
        {
            "ok": True,
            "project": (updated or project).to_dict(),
            "creator_total": revenue_tracker.total_earnings(project.creator),
        }
    )


@pikkaio_bp.route("/api/intents/<intent_id>/tending", methods=["GET"])
def today_task(intent_id: str):
    task = tending_engine.get_or_generate(intent_id)
    return jsonify({"ok": True, "task": task, "summary": tending_engine.summary(intent_id)})


@pikkaio_bp.route("/api/intents/<intent_id>/tending/complete", methods=["POST"])
def complete_task(intent_id: str):
    payload = request.get_json(silent=True) or {}
    task_id = (payload.get("task_id") or "").strip()
    if not task_id:
        return jsonify({"error": "task_id required"}), 400
    result = tending_engine.mark_complete(intent_id, task_id)
    if not result.get("ok"):
        return jsonify(result), 400
    get_project_engine().record_signal(intent_id, "tending_complete", 1.0)
    return jsonify(result)
