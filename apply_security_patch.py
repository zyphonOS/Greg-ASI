"""
GregASI Security Patch
Run from: gregasi-ecosystem/
Command:  python apply_security_patch.py
"""
import re
from pathlib import Path

ROOT = Path(__file__).parent

# ─────────────────────────────────────────────
# PATCH 1 — user_auth.py
# ─────────────────────────────────────────────
auth_path = ROOT / "user_auth.py"
auth_src = auth_path.read_text(encoding="utf-8")

# FIX 1a: _determine_role — kill the founder_count == 0 loophole
# Anyone who hits signup on a fresh DB could claim founder. Removed entirely.
# Now: founder role ONLY if email is in FOUNDER_EMAILS env var.
old_determine_role = '''def _determine_role(email: str, requested_role: str | None = None) -> str:
    clean_email = str(email or "").strip().lower()
    clean_requested = str(requested_role or "builder").strip().lower() or "builder"
    founder_emails = _founder_emails()
    with _conn() as conn:
        founder_count = int(conn.execute("SELECT COUNT(*) FROM users WHERE role = 'founder'").fetchone()[0] or 0)
    if clean_requested == "founder" and (clean_email in founder_emails or founder_count == 0):
        return "founder"
    if clean_email in founder_emails:
        return "founder"
    if clean_requested in {"admin", "builder", "treasury", "community"}:
        return clean_requested
    return "builder"'''

new_determine_role = '''def _determine_role(email: str, requested_role: str | None = None) -> str:
    """
    Role assignment rules (order is authoritative):
    1. If email is in FOUNDER_EMAILS env var → always founder, no exceptions.
    2. Public signups → always builder, regardless of what they request.
    The old founder_count == 0 bypass has been removed. It allowed any stranger
    to claim founder on a fresh or wiped database. Never again.
    """
    clean_email = str(email or "").strip().lower()
    clean_requested = str(requested_role or "builder").strip().lower() or "builder"
    founder_emails = _founder_emails()
    # Founders are declared by env var only — not by request, not by DB state
    if clean_email in founder_emails:
        return "founder"
    # Public users get builder. Admin/treasury/community only via env-declared emails in future.
    if clean_requested in {"builder"}:
        return "builder"
    return "builder"'''

assert old_determine_role in auth_src, "PATCH 1a FAILED: _determine_role not found as expected"
auth_src = auth_src.replace(old_determine_role, new_determine_role)
print("✓ PATCH 1a applied: _determine_role — founder_count==0 loophole removed")

# FIX 1b: signup POST — ignore role from request body entirely
# Users were able to POST {"role": "admin"} and get admin. Removed.
old_signup_post = '''        requested_role = str(payload.get("role") or "builder").strip().lower() or "builder"
        try:
            user = create_user(email, password, requested_role=requested_role)'''

new_signup_post = '''        # Role is NEVER taken from user input. _determine_role assigns based on FOUNDER_EMAILS only.
        try:
            user = create_user(email, password, requested_role="builder")'''

assert old_signup_post in auth_src, "PATCH 1b FAILED: signup POST role line not found"
auth_src = auth_src.replace(old_signup_post, new_signup_post)
print("✓ PATCH 1b applied: signup POST — user-supplied role ignored")

# FIX 1c: signup GET form — remove the role dropdown from the UI
# No point showing a control that does nothing.
old_signup_form = '''        <form method="post" action="/signup">
          <div class="row"><label>Email</label><input name="email" type="email" required></div>
          <div class="row"><label>Password</label><input name="password" type="password" minlength="8" required></div>
          <div class="row"><label>Role</label><select name="role"><option value="builder">Builder</option><option value="founder">Founder</option><option value="admin">Admin</option></select></div>
          <button type="submit">Create Account</button>
        </form>
        <p class="note">Already registered? <a href="/login">Log in</a>.</p>'''

new_signup_form = '''        <form method="post" action="/signup">
          <div class="row"><label>Email</label><input name="email" type="email" required></div>
          <div class="row"><label>Password</label><input name="password" type="password" minlength="8" required></div>
          <button type="submit">Create Account</button>
        </form>
        <p class="note">Already registered? <a href="/login">Log in</a>.</p>'''

assert old_signup_form in auth_src, "PATCH 1c FAILED: signup GET form not found"
auth_src = auth_src.replace(old_signup_form, new_signup_form)
print("✓ PATCH 1c applied: signup form — role dropdown removed")

# FIX 1d: signup error form — also remove role dropdown from error state
old_signup_error_form = '''                  <div class="row"><label>Role</label><select name="role"><option value="builder">Builder</option><option value="founder">Founder</option><option value="admin">Admin</option></select></div>
                  <button type="submit">Create Account</button>'''

new_signup_error_form = '''                  <button type="submit">Create Account</button>'''

if old_signup_error_form in auth_src:
    auth_src = auth_src.replace(old_signup_error_form, new_signup_error_form)
    print("✓ PATCH 1d applied: signup error form — role dropdown removed")
else:
    print("~ PATCH 1d skipped: error form role dropdown already absent")

auth_path.write_text(auth_src, encoding="utf-8")
print("✓ user_auth.py saved\n")

# ─────────────────────────────────────────────
# PATCH 2 — payment_routes.py
# ─────────────────────────────────────────────
pay_path = ROOT / "payment_routes.py"
pay_src = pay_path.read_text(encoding="utf-8")

# FIX 2a: Kill the hardcoded default API key
# "greg-public-dev-key" is published in the docs. Anyone can use it.
# New default is "" — if env var not set, key auth is disabled entirely
# and mock_confirm cannot be triggered.
old_default_key = 'PUBLIC_PAYMENT_API_KEY = os.getenv("PUBLIC_PAYMENT_API_KEY", "greg-public-dev-key")'
new_default_key = (
    '# SECURITY: No hardcoded fallback. Set PUBLIC_PAYMENT_API_KEY in Railway env vars.\n'
    '# If unset, _api_key_valid() returns False and mock_confirm is permanently disabled.\n'
    'PUBLIC_PAYMENT_API_KEY = os.getenv("PUBLIC_PAYMENT_API_KEY", "")'
)

assert old_default_key in pay_src, "PATCH 2a FAILED: hardcoded key line not found"
pay_src = pay_src.replace(old_default_key, new_default_key)
print("✓ PATCH 2a applied: hardcoded 'greg-public-dev-key' default removed")

# FIX 2b: Kill mock_confirm entirely
# This block let anyone with the (now-public) API key confirm fake payments.
old_mock_block = '''        if _api_key_valid() and (
            str(payload.get("mock_confirm") or "").lower() == "true"
            or tx_hash.startswith("mock_")
        ):
            verification = {
                "ok": True,
                "mock": True,
                "from": str(payload.get("wallet_address") or payment.get("wallet_address") or ""),
                "to": TREASURY_WALLET,
                "amount_usdc": float(payment.get("amount_usdc") or 0.0),
            }
        else:
            verification = _verify_usdc_transfer(
                tx_hash,
                expected_to=TREASURY_WALLET,
                expected_amount_usdc=float(payment.get("amount_usdc") or 0.0),
                expected_from=str(payload.get("wallet_address") or payment.get("wallet_address") or "").strip(),
            )'''

new_mock_block = '''        # SECURITY: mock_confirm removed. Every payment requires a real on-chain tx_hash.
        verification = _verify_usdc_transfer(
            tx_hash,
            expected_to=TREASURY_WALLET,
            expected_amount_usdc=float(payment.get("amount_usdc") or 0.0),
            expected_from=str(payload.get("wallet_address") or payment.get("wallet_address") or "").strip(),
        )'''

assert old_mock_block in pay_src, "PATCH 2b FAILED: mock_confirm block not found as expected"
pay_src = pay_src.replace(old_mock_block, new_mock_block)
print("✓ PATCH 2b applied: mock_confirm bypass permanently removed")

pay_path.write_text(pay_src, encoding="utf-8")
print("✓ payment_routes.py saved\n")

print("=" * 55)
print("ALL PATCHES APPLIED SUCCESSFULLY")
print("=" * 55)
print("""
NEXT STEP — Set these 3 env vars in Railway dashboard NOW:

  FOUNDER_EMAILS     = your-email@domain.com,silas-email@domain.com
  PUBLIC_PAYMENT_API_KEY = (generate with: python -c "import secrets; print(secrets.token_urlsafe(32))")
  SECRET_KEY         = (generate with: python -c "import secrets; print(secrets.token_urlsafe(64))")

Then deploy:
  git add -A
  git commit -m "security: close auth role bypass, kill mock payments, remove hardcoded api key"
  git push
""")
