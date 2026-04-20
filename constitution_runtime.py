from __future__ import annotations

import os
from typing import Any, Iterable


BUILDER_SHARE_PCT = 0.40
GREG_SHARE_PCT = 0.40
TREASURY_SHARE_PCT = 0.20
FOUNDER_MONTHLY_STIPEND_TARGET = 10_000.0
FOUNDER_MONTHLY_REVENUE_THRESHOLD = 50_000.0
FOUNDER_SECURITY_FUND_MONTHS = 12
HUMANITARIAN_CAP_RATE = 0.05
HUMANITARIAN_CAP_FLOOR = 1_000.0
DEFAULT_ROLE = "guest"


def _money(value: float) -> float:
    return round(max(float(value or 0.0), 0.0), 2)


def constitutional_revenue_allocation(
    gross_revenue: float,
    *,
    treasury_balance: float = 0.0,
    projected_builder_income: float | None = None,
    quarter_gross_revenue: float | None = None,
) -> dict[str, float]:
    gross = _money(gross_revenue)
    builder_share = _money(gross * BUILDER_SHARE_PCT)
    greg_share = _money(gross * GREG_SHARE_PCT)
    treasury_share = _money(gross * TREASURY_SHARE_PCT)

    if gross >= FOUNDER_MONTHLY_REVENUE_THRESHOLD:
        combined_stipend = FOUNDER_MONTHLY_STIPEND_TARGET
    else:
        combined_stipend = _money(
            FOUNDER_MONTHLY_STIPEND_TARGET * (gross / FOUNDER_MONTHLY_REVENUE_THRESHOLD)
            if FOUNDER_MONTHLY_REVENUE_THRESHOLD
            else 0.0
        )

    founder_stipend_each = _money(combined_stipend / 2.0)
    projected_builder = _money(builder_share if projected_builder_income is None else projected_builder_income)
    founder_security_target = _money(
        (combined_stipend * FOUNDER_SECURITY_FUND_MONTHS)
        + (projected_builder * FOUNDER_SECURITY_FUND_MONTHS)
    )
    current_security_fund = _money(min(treasury_balance, founder_security_target))
    stipend_coverage_months = round(
        (current_security_fund / combined_stipend) if combined_stipend else 0.0,
        2,
    )

    quarter_gross = gross if quarter_gross_revenue is None else _money(quarter_gross_revenue)
    humanitarian_cap = _money(max(quarter_gross * HUMANITARIAN_CAP_RATE, HUMANITARIAN_CAP_FLOOR))
    humanitarian_placeholder = _money(min(treasury_share, humanitarian_cap))
    treasury_operating_balance = _money(max(treasury_share - humanitarian_placeholder, 0.0))

    return {
        "gross_revenue": gross,
        "builder_share": builder_share,
        "greg_share": greg_share,
        "treasury_share": treasury_share,
        "builder_share_pct": BUILDER_SHARE_PCT,
        "greg_share_pct": GREG_SHARE_PCT,
        "treasury_share_pct": TREASURY_SHARE_PCT,
        "combined_founder_stipend": combined_stipend,
        "founder_stipend_each": founder_stipend_each,
        "founder_security_fund_target": founder_security_target,
        "founder_security_fund_current": current_security_fund,
        "founder_security_coverage_months": stipend_coverage_months,
        "humanitarian_quarter_cap": humanitarian_cap,
        "humanitarian_placeholder_allocation": humanitarian_placeholder,
        "treasury_operating_balance": treasury_operating_balance,
    }


def build_auth_state(session_like: dict[str, Any] | Any | None) -> dict[str, Any]:
    session_like = session_like or {}
    logged_in = bool(session_like.get("logged_in"))
    raw_role = str(session_like.get("role") or DEFAULT_ROLE).strip().lower() or DEFAULT_ROLE
    roles = session_like.get("roles") or ([raw_role] if raw_role else [DEFAULT_ROLE])
    if isinstance(roles, str):
        roles = [roles]
    roles = [str(role).strip().lower() for role in roles if str(role).strip()]
    if raw_role not in roles:
        roles.insert(0, raw_role)

    role_labels = {
        "guest": "Guest Preview",
        "builder": "Builder",
        "founder": "Founder",
        "treasury": "Treasury Steward",
        "community": "Community Council",
        "admin": "Executive Steward",
    }
    return {
        "logged_in": logged_in,
        "role": raw_role,
        "roles": roles,
        "role_label": role_labels.get(raw_role, raw_role.title() or "Guest Preview"),
        "placeholder_mode": not logged_in,
        "login_ready_note": (
            "Authentication placeholder active. Session role wiring is ready for live auth."
            if not logged_in
            else "Authenticated session active."
        ),
    }


def build_protection_state(
    session_like: dict[str, Any] | Any | None,
    *,
    surface: str,
    required_roles: Iterable[str],
) -> dict[str, Any]:
    auth = build_auth_state(session_like)
    required = [str(role).strip().lower() for role in required_roles if str(role).strip()]
    authorized = auth["logged_in"] and any(role in auth["roles"] for role in required)
    enforced = os.getenv("GREG_ENFORCE_ROLE_AUTH", "false").lower() == "true"
    preview_mode = not authorized
    return {
        "surface": surface,
        "required_roles": required,
        "required_roles_label": ", ".join(role.title() for role in required),
        "authorized": authorized,
        "preview_mode": preview_mode,
        "enforced": enforced,
        "message": (
            f"{surface} is constitution-sensitive. "
            f"Required role: {', '.join(required)}. "
            "Preview mode is visible until live authentication is enforced."
        ),
    }
