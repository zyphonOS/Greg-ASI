from __future__ import annotations

from flask import Blueprint, render_template

from layers.legacy.pikkaio.routes import _builder_id, _builder_intents


revenue_bp = Blueprint("pikkaio_revenue", __name__)
GREG_SHARE_PCT = 0.05


def _is_converged(intent) -> bool:
    return float(intent.progress or 0.0) >= 1.0 or intent.status in {"completed", "converged"}


@revenue_bp.route("/revenue")
def revenue():
    builder_id = _builder_id(create=True)
    intents = _builder_intents(builder_id)

    confirmed_revenue = round(sum(float(intent.revenue_usd or 0.0) for intent in intents), 2)
    pending_revenue = round(
        sum(
            max(float(intent.revenue_target or 0.0) - float(intent.revenue_usd or 0.0), 0.0)
            for intent in intents
            if not _is_converged(intent)
        ),
        2,
    )
    greg_share_confirmed = round(
        sum(float(intent.revenue_usd or 0.0) * GREG_SHARE_PCT for intent in intents if _is_converged(intent)),
        2,
    )
    greg_share_pending = round(pending_revenue * GREG_SHARE_PCT, 2)

    lines = []
    convergence_events = []
    for intent in intents:
        converged = _is_converged(intent)
        pending_line = max(float(intent.revenue_target or 0.0) - float(intent.revenue_usd or 0.0), 0.0)
        line = {
            "intent_id": intent.id,
            "description": intent.description,
            "status": intent.status,
            "revenue_usd": round(float(intent.revenue_usd or 0.0), 2),
            "revenue_target": round(float(intent.revenue_target or 0.0), 2),
            "pending_revenue": round(pending_line, 2),
            "greg_share": round(float(intent.revenue_usd or 0.0) * GREG_SHARE_PCT, 2),
            "projected_share": round(pending_line * GREG_SHARE_PCT, 2),
            "converged": converged,
            "updated_at": intent.updated_at,
        }
        lines.append(line)
        if converged:
            convergence_events.append(line)

    lines.sort(key=lambda item: (0 if item["converged"] else 1, -item["revenue_usd"]))

    revenue_state = {
        "builder_id": builder_id,
        "confirmed_revenue": confirmed_revenue,
        "pending_revenue": pending_revenue,
        "greg_share_confirmed": greg_share_confirmed,
        "greg_share_pending": greg_share_pending,
        "share_pct": GREG_SHARE_PCT,
        "has_convergence": bool(convergence_events),
        "convergence_count": len(convergence_events),
        "lines_total": len(lines),
    }

    return render_template(
        "revenue.html",
        revenue=revenue_state,
        lines=lines,
        convergence_events=convergence_events,
    )
