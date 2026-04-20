from __future__ import annotations

from flask import Blueprint, render_template, session

from constitution_runtime import build_protection_state, constitutional_revenue_allocation
from layers.legacy.pikkaio.routes import _builder_id, _builder_intents


revenue_bp = Blueprint("pikkaio_revenue", __name__)


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
    finance = constitutional_revenue_allocation(
        confirmed_revenue,
        treasury_balance=confirmed_revenue * 0.2,
        quarter_gross_revenue=confirmed_revenue,
    )
    projected_finance = constitutional_revenue_allocation(
        pending_revenue,
        treasury_balance=finance["treasury_share"],
        quarter_gross_revenue=confirmed_revenue + pending_revenue,
    )

    lines = []
    convergence_events = []
    for intent in intents:
        converged = _is_converged(intent)
        pending_line = max(float(intent.revenue_target or 0.0) - float(intent.revenue_usd or 0.0), 0.0)
        line_finance = constitutional_revenue_allocation(
            float(intent.revenue_usd or 0.0),
            treasury_balance=float(intent.revenue_usd or 0.0) * 0.2,
        )
        projected_line_finance = constitutional_revenue_allocation(
            pending_line,
            treasury_balance=line_finance["treasury_share"],
        )
        line = {
            "intent_id": intent.id,
            "description": intent.description,
            "status": intent.status,
            "revenue_usd": round(float(intent.revenue_usd or 0.0), 2),
            "revenue_target": round(float(intent.revenue_target or 0.0), 2),
            "pending_revenue": round(pending_line, 2),
            "builder_share": line_finance["builder_share"],
            "greg_share": line_finance["greg_share"],
            "treasury_share": line_finance["treasury_share"],
            "projected_builder_share": projected_line_finance["builder_share"],
            "projected_greg_share": projected_line_finance["greg_share"],
            "projected_treasury_share": projected_line_finance["treasury_share"],
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
        "builder_share_confirmed": finance["builder_share"],
        "greg_share_confirmed": finance["greg_share"],
        "treasury_share_confirmed": finance["treasury_share"],
        "builder_share_pending": projected_finance["builder_share"],
        "greg_share_pending": projected_finance["greg_share"],
        "treasury_share_pending": projected_finance["treasury_share"],
        "share_pct": finance["greg_share_pct"],
        "has_convergence": bool(convergence_events),
        "convergence_count": len(convergence_events),
        "lines_total": len(lines),
        "founder_security_fund_target": finance["founder_security_fund_target"],
        "founder_security_fund_current": finance["founder_security_fund_current"],
        "founder_stipend_each": finance["founder_stipend_each"],
        "humanitarian_quarter_cap": finance["humanitarian_quarter_cap"],
        "humanitarian_placeholder_allocation": finance["humanitarian_placeholder_allocation"],
    }

    return render_template(
        "revenue.html",
        finance=finance,
        revenue=revenue_state,
        lines=lines,
        convergence_events=convergence_events,
        projected_finance=projected_finance,
        protection=build_protection_state(
            session,
            surface="Revenue Ledger",
            required_roles=("founder", "treasury", "admin"),
        ),
    )
