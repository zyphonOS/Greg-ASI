from __future__ import annotations

import json
import os
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Iterable

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    jsonify,
    redirect,
    render_template_string,
    request,
    session,
    url_for,
)
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from core.utils import data_path, ensure_directory


AUTH_DB_PATH = data_path("auth.db")
BASE_SEPOLIA_CHAIN_ID = 84532
BASE_SEPOLIA_CHAIN_HEX = hex(BASE_SEPOLIA_CHAIN_ID)
BASE_SEPOLIA_RPC = os.getenv("BASE_RPC_URL", "https://sepolia.base.org")

auth_bp = Blueprint("auth", __name__)
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.session_protection = "strong"


@dataclass
class AuthUser(UserMixin):
    id: str
    email: str
    role: str
    wallet_address: str | None
    created_at: str
    last_active: str
    premium_until: str | None

    @property
    def is_premium(self) -> bool:
        if not self.premium_until:
            return False
        try:
            return datetime.fromisoformat(self.premium_until) > datetime.now(timezone.utc)
        except Exception:
            return False


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conn() -> sqlite3.Connection:
    ensure_directory(Path(AUTH_DB_PATH).parent)
    conn = sqlite3.connect(AUTH_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_auth_db() -> None:
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'builder',
                wallet_address TEXT,
                created_at TEXT NOT NULL,
                last_active TEXT NOT NULL,
                premium_until TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                last_active TEXT NOT NULL,
                user_agent TEXT,
                ip_address TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS payments (
                payment_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                amount_usdc REAL NOT NULL,
                service TEXT NOT NULL,
                status TEXT NOT NULL,
                wallet_address TEXT,
                tx_hash TEXT,
                chain_id INTEGER,
                network TEXT,
                created_at TEXT NOT NULL,
                confirmed_at TEXT,
                raw_request TEXT,
                split_json TEXT,
                metadata TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status)")


def _row_to_user(row: sqlite3.Row | None) -> AuthUser | None:
    if not row:
        return None
    return AuthUser(
        id=str(row["id"]),
        email=str(row["email"]),
        role=str(row["role"] or "builder"),
        wallet_address=row["wallet_address"],
        created_at=str(row["created_at"]),
        last_active=str(row["last_active"]),
        premium_until=row["premium_until"],
    )


def get_user_by_id(user_id: str | int | None) -> AuthUser | None:
    if not user_id:
        return None
    with _conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (str(user_id),)).fetchone()
    return _row_to_user(row)


def get_user_by_email(email: str) -> AuthUser | None:
    clean_email = str(email or "").strip().lower()
    if not clean_email:
        return None
    with _conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (clean_email,)).fetchone()
    return _row_to_user(row)


def get_user_record(user_id: str | int | None) -> dict[str, Any] | None:
    user = get_user_by_id(user_id)
    if not user:
        return None
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "wallet_address": user.wallet_address,
        "created_at": user.created_at,
        "last_active": user.last_active,
        "premium_until": user.premium_until,
        "is_premium": user.is_premium,
    }


def _founder_emails() -> set[str]:
    configured = os.getenv("FOUNDER_EMAILS", "")
    emails = {item.strip().lower() for item in configured.split(",") if item.strip()}
    return emails


def _determine_role(email: str, requested_role: str | None = None) -> str:
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
    return "builder"


def create_user(email: str, password: str, requested_role: str | None = None) -> AuthUser:
    clean_email = str(email or "").strip().lower()
    if not clean_email:
        raise ValueError("email is required")
    if len(str(password or "")) < 8:
        raise ValueError("password must be at least 8 characters")
    if get_user_by_email(clean_email):
        raise ValueError("email already registered")

    role = _determine_role(clean_email, requested_role)
    now = _utc_now()
    password_hash = generate_password_hash(password)
    with _conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO users (email, password_hash, role, wallet_address, created_at, last_active, premium_until)
            VALUES (?, ?, ?, NULL, ?, ?, NULL)
            """,
            (clean_email, password_hash, role, now, now),
        )
        user_id = cursor.lastrowid
    user = get_user_by_id(user_id)
    if not user:
        raise RuntimeError("Unable to load newly created user.")
    return user


def verify_user(email: str, password: str) -> AuthUser | None:
    clean_email = str(email or "").strip().lower()
    with _conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (clean_email,)).fetchone()
    if not row:
        return None
    if not check_password_hash(str(row["password_hash"]), str(password or "")):
        return None
    return _row_to_user(row)


def update_last_active(user_id: str | int) -> None:
    now = _utc_now()
    with _conn() as conn:
        conn.execute("UPDATE users SET last_active = ? WHERE id = ?", (now, str(user_id)))


def attach_wallet(user_id: str | int, wallet_address: str) -> AuthUser:
    clean_wallet = str(wallet_address or "").strip()
    if not clean_wallet:
        raise ValueError("wallet_address is required")
    with _conn() as conn:
        conn.execute(
            "UPDATE users SET wallet_address = ?, last_active = ? WHERE id = ?",
            (clean_wallet, _utc_now(), str(user_id)),
        )
    user = get_user_by_id(user_id)
    if not user:
        raise RuntimeError("User not found after wallet update.")
    return user


def set_user_premium(user_id: str | int, *, duration_days: int = 30) -> AuthUser:
    premium_until = (datetime.now(timezone.utc) + timedelta(days=duration_days)).isoformat()
    with _conn() as conn:
        conn.execute(
            "UPDATE users SET premium_until = ?, last_active = ? WHERE id = ?",
            (premium_until, _utc_now(), str(user_id)),
        )
    user = get_user_by_id(user_id)
    if not user:
        raise RuntimeError("User not found after premium update.")
    return user


def create_session_record(user_id: str | int) -> str:
    session_id = secrets.token_urlsafe(24)
    now = _utc_now()
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO sessions (id, user_id, created_at, last_active, user_agent, ip_address)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                int(user_id),
                now,
                now,
                request.headers.get("User-Agent", ""),
                request.headers.get("X-Forwarded-For", request.remote_addr or ""),
            ),
        )
    session["greg_session_id"] = session_id
    session["logged_in"] = True
    return session_id


def touch_session_record() -> None:
    session_id = session.get("greg_session_id")
    if not session_id or not current_user.is_authenticated:
        return
    now = _utc_now()
    with _conn() as conn:
        conn.execute("UPDATE sessions SET last_active = ? WHERE id = ?", (now, session_id))
    update_last_active(current_user.id)


def delete_session_record() -> None:
    session_id = session.get("greg_session_id")
    if session_id:
        with _conn() as conn:
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    session.pop("greg_session_id", None)
    session["logged_in"] = False


def create_payment_record(
    *,
    user_id: str | int,
    amount_usdc: float,
    service: str,
    wallet_address: str | None,
    chain_id: int,
    network: str,
    raw_request: dict[str, Any] | None = None,
    split: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    payment_id = "pay_" + secrets.token_hex(12)
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO payments (
                payment_id, user_id, amount_usdc, service, status, wallet_address,
                tx_hash, chain_id, network, created_at, confirmed_at, raw_request, split_json, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, NULL, ?, ?, ?)
            """,
            (
                payment_id,
                int(user_id),
                round(float(amount_usdc or 0.0), 6),
                str(service or "intent"),
                "pending",
                wallet_address,
                int(chain_id),
                str(network or "Base Testnet"),
                _utc_now(),
                json.dumps(raw_request or {}, ensure_ascii=True),
                json.dumps(split or {}, ensure_ascii=True),
                json.dumps(metadata or {}, ensure_ascii=True),
            ),
        )
    return payment_id


def get_payment(payment_id: str) -> dict[str, Any] | None:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM payments WHERE payment_id = ?", (str(payment_id),)).fetchone()
    if not row:
        return None
    payload = dict(row)
    for key in ("raw_request", "split_json", "metadata"):
        try:
            payload[key] = json.loads(payload.get(key) or "{}")
        except Exception:
            payload[key] = {}
    return payload


def confirm_payment(payment_id: str, tx_hash: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    payment = get_payment(payment_id)
    if not payment:
        raise ValueError("payment not found")
    merged_metadata = dict(payment.get("metadata") or {})
    merged_metadata.update(metadata or {})
    with _conn() as conn:
        conn.execute(
            """
            UPDATE payments
            SET status = 'confirmed', tx_hash = ?, confirmed_at = ?, metadata = ?
            WHERE payment_id = ?
            """,
            (
                str(tx_hash or "").strip(),
                _utc_now(),
                json.dumps(merged_metadata, ensure_ascii=True),
                str(payment_id),
            ),
        )
    confirmed = get_payment(payment_id)
    if not confirmed:
        raise RuntimeError("Unable to reload confirmed payment.")
    return confirmed


def list_user_payments(user_id: str | int, *, limit: int = 20) -> list[dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM payments WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (int(user_id), int(limit)),
        ).fetchall()
    results: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row)
        for key in ("raw_request", "split_json", "metadata"):
            try:
                payload[key] = json.loads(payload.get(key) or "{}")
            except Exception:
                payload[key] = {}
        results.append(payload)
    return results


def payment_summary_for_user(user_id: str | int) -> dict[str, Any]:
    payments = list_user_payments(user_id, limit=100)
    confirmed = [row for row in payments if row.get("status") == "confirmed"]
    pending = [row for row in payments if row.get("status") == "pending"]
    return {
        "confirmed_usdc": round(sum(float(row.get("amount_usdc") or 0.0) for row in confirmed), 2),
        "pending_usdc": round(sum(float(row.get("amount_usdc") or 0.0) for row in pending), 2),
        "payments": payments,
    }


def all_payments_summary(*, limit: int = 100) -> dict[str, Any]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM payments
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
    payments: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row)
        for key in ("raw_request", "split_json", "metadata"):
            try:
                payload[key] = json.loads(payload.get(key) or "{}")
            except Exception:
                payload[key] = {}
        payments.append(payload)
    confirmed = [row for row in payments if row.get("status") == "confirmed"]
    pending = [row for row in payments if row.get("status") == "pending"]
    return {
        "confirmed_usdc": round(sum(float(row.get("amount_usdc") or 0.0) for row in confirmed), 2),
        "pending_usdc": round(sum(float(row.get("amount_usdc") or 0.0) for row in pending), 2),
        "confirmed_count": len(confirmed),
        "pending_count": len(pending),
        "payments": payments,
    }


def auth_state_for_current_user() -> dict[str, Any]:
    if current_user.is_authenticated:
        return {
            "logged_in": True,
            "role": current_user.role,
            "roles": [current_user.role],
            "role_label": current_user.role.title(),
            "email": current_user.email,
            "wallet_address": current_user.wallet_address,
            "is_premium": current_user.is_premium,
        }
    return {
        "logged_in": False,
        "role": "guest",
        "roles": ["guest"],
        "role_label": "Guest Preview",
        "email": "",
        "wallet_address": None,
        "is_premium": False,
    }


def role_required(*roles: str):
    allowed = {str(role).strip().lower() for role in roles if str(role).strip()}

    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapped(*args, **kwargs):
            current_role = str(getattr(current_user, "role", "guest")).strip().lower()
            if current_role not in allowed:
                if request.path.startswith("/api/") or request.accept_mimetypes.best == "application/json":
                    return jsonify({"ok": False, "error": "Forbidden"}), 403
                abort(403)
            return fn(*args, **kwargs)

        return wrapped

    return decorator


def login_or_json():
    if request.path.startswith("/api/") or request.accept_mimetypes.best == "application/json":
        return jsonify({"ok": False, "error": "Authentication required"}), 401
    return redirect(url_for("auth.login", next=request.url))


@login_manager.user_loader
def load_user(user_id: str) -> AuthUser | None:
    return get_user_by_id(user_id)


@login_manager.unauthorized_handler
def _handle_unauthorized():
    return login_or_json()


def protected_page_roles() -> dict[str, tuple[str, ...]]:
    return {
        "/dashboard": ("builder", "admin", "founder"),
        "/revenue": ("builder", "admin", "founder", "treasury"),
        "/treasury": ("builder", "admin", "founder", "treasury"),
        "/zyphonos/": ("builder", "admin", "founder"),
        "/zyphonos": ("builder", "admin", "founder"),
        "/founder-office": ("founder",),
        "/chat": ("builder", "admin", "founder", "treasury", "community"),
        "/profile": ("builder", "admin", "founder", "treasury", "community"),
        "/connect-wallet": ("builder", "admin", "founder", "treasury", "community"),
    }


def init_auth(app) -> None:
    init_auth_db()
    login_manager.init_app(app)

    @app.before_request
    def _enforce_access_rules():
        path = request.path.rstrip("/") or "/"
        for protected_path, roles in protected_page_roles().items():
            if path != protected_path.rstrip("/"):
                continue
            if not current_user.is_authenticated:
                return login_or_json()
            current_role = str(getattr(current_user, "role", "guest")).strip().lower()
            if current_role not in {role.lower() for role in roles}:
                if request.path.startswith("/api/"):
                    return jsonify({"ok": False, "error": "Forbidden"}), 403
                abort(403)
            touch_session_record()
            break


def _render_auth_page(title: str, body: str) -> str:
    return render_template_string(
        """
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <title>{{ title }}</title>
          <style>
            body { font-family: Arial, sans-serif; max-width: 760px; margin: 3rem auto; padding: 0 1rem; background:#0b0b0f; color:#e8e8f0; }
            form { display:grid; gap: 1rem; background:#111118; border:1px solid rgba(255,255,255,0.08); padding:1.25rem; }
            input, select, button { padding:0.85rem; font-size:1rem; }
            input, select { background:#060608; color:#e8e8f0; border:1px solid rgba(255,255,255,0.12); }
            button { background:#00ff9d; color:#060608; border:0; cursor:pointer; }
            a { color:#00ff9d; }
            .note { color:#9898b0; margin: 0.5rem 0 1rem; }
            .row { display:grid; gap:0.35rem; }
          </style>
        </head>
        <body>
          <h1>{{ title }}</h1>
          <div class="note">Production-ready auth is active. Founder and builder roles are enforced at the route layer.</div>
          {{ body|safe }}
        </body>
        </html>
        """,
        title=title,
        body=body,
    )


def _wants_json_response() -> bool:
    return bool(request.is_json) or request.path.startswith("/api/") or request.accept_mimetypes.best == "application/json"


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        payload = request.get_json(silent=True) or request.form
        email = str(payload.get("email") or "").strip().lower()
        password = str(payload.get("password") or "")
        requested_role = str(payload.get("role") or "builder").strip().lower() or "builder"
        try:
            user = create_user(email, password, requested_role=requested_role)
            login_user(user, remember=True)
            create_session_record(user.id)
            if _wants_json_response():
                return jsonify({"ok": True, "user": get_user_record(user.id), "next": url_for("auth.profile")})
            return redirect(url_for("auth.profile"))
        except Exception as exc:
            if _wants_json_response():
                return jsonify({"ok": False, "error": str(exc)}), 400
            return _render_auth_page(
                "Sign Up",
                f"""
                <p class="note" style="color:#ff9500;">{exc}</p>
                <form method="post" action="/signup">
                  <div class="row"><label>Email</label><input name="email" type="email" value="{email}" required></div>
                  <div class="row"><label>Password</label><input name="password" type="password" minlength="8" required></div>
                  <div class="row"><label>Role</label><select name="role"><option value="builder">Builder</option><option value="founder">Founder</option><option value="admin">Admin</option></select></div>
                  <button type="submit">Create Account</button>
                </form>
                <p class="note">Already registered? <a href="/login">Log in</a>.</p>
                """,
            ), 400

    return _render_auth_page(
        "Sign Up",
        """
        <form method="post" action="/signup">
          <div class="row"><label>Email</label><input name="email" type="email" required></div>
          <div class="row"><label>Password</label><input name="password" type="password" minlength="8" required></div>
          <div class="row"><label>Role</label><select name="role"><option value="builder">Builder</option><option value="founder">Founder</option><option value="admin">Admin</option></select></div>
          <button type="submit">Create Account</button>
        </form>
        <p class="note">Already registered? <a href="/login">Log in</a>.</p>
        """,
    )


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        payload = request.get_json(silent=True) or request.form
        email = str(payload.get("email") or "").strip().lower()
        password = str(payload.get("password") or "")
        user = verify_user(email, password)
        if not user:
            if _wants_json_response():
                return jsonify({"ok": False, "error": "Invalid credentials"}), 401
            return _render_auth_page(
                "Log In",
                f"""
                <p class="note" style="color:#ff9500;">Invalid credentials</p>
                <form method="post" action="/login">
                  <div class="row"><label>Email</label><input name="email" type="email" value="{email}" required></div>
                  <div class="row"><label>Password</label><input name="password" type="password" required></div>
                  <button type="submit">Log In</button>
                </form>
                <p class="note">Need an account? <a href="/signup">Sign up</a>.</p>
                """,
            ), 401
        login_user(user, remember=True)
        create_session_record(user.id)
        update_last_active(user.id)
        next_url = request.args.get("next") or url_for("auth.profile")
        if _wants_json_response():
            return jsonify({"ok": True, "user": get_user_record(user.id), "next": next_url})
        return redirect(next_url)

    return _render_auth_page(
        "Log In",
        """
        <form method="post" action="/login">
          <div class="row"><label>Email</label><input name="email" type="email" required></div>
          <div class="row"><label>Password</label><input name="password" type="password" required></div>
          <button type="submit">Log In</button>
        </form>
        <p class="note">Need an account? <a href="/signup">Sign up</a>.</p>
        """,
    )


@auth_bp.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    delete_session_record()
    logout_user()
    return redirect(url_for("home"))


@auth_bp.route("/profile", methods=["GET"])
@login_required
def profile():
    summary = payment_summary_for_user(current_user.id)
    return _render_auth_page(
        "Profile",
        f"""
        <div class="note">Signed in as <strong>{current_user.email}</strong> · role <strong>{current_user.role}</strong></div>
        <div class="note">Wallet: <strong>{current_user.wallet_address or 'not connected'}</strong></div>
        <div class="note">Premium until: <strong>{current_user.premium_until or 'not active'}</strong></div>
        <div class="note">Confirmed USDC: <strong>{summary['confirmed_usdc']:.2f}</strong> · Pending USDC: <strong>{summary['pending_usdc']:.2f}</strong></div>
        <p><a href="/connect-wallet">Connect wallet</a> · <a href="/chat">Open chat</a> · <a href="/logout">Log out</a></p>
        """,
    )


@auth_bp.route("/connect-wallet", methods=["GET", "POST"])
@login_required
def connect_wallet():
    if request.method == "POST":
        payload = request.get_json(silent=True) or request.form
        wallet_address = str(payload.get("wallet_address") or "").strip()
        try:
            user = attach_wallet(current_user.id, wallet_address)
            return jsonify({"ok": True, "wallet_address": user.wallet_address, "chain_id": BASE_SEPOLIA_CHAIN_ID})
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

    return _render_auth_page(
        "Connect Wallet",
        f"""
        <div class="note">Connect a Base-compatible EIP-1193 wallet (MetaMask, Coinbase Wallet, or compatible mobile wallet) and bind it to your Greg account.</div>
        <div id="wallet-state" class="note">Current wallet: <strong>{current_user.wallet_address or 'not connected'}</strong></div>
        <button id="connect-wallet-btn" type="button">Connect Base Wallet</button>
        <script>
          const button = document.getElementById("connect-wallet-btn");
          const state = document.getElementById("wallet-state");
          button.addEventListener("click", async () => {{
            if (!window.ethereum) {{
              state.textContent = "No injected wallet detected.";
              return;
            }}
            try {{
              await window.ethereum.request({{ method: "wallet_switchEthereumChain", params: [{{ chainId: "{BASE_SEPOLIA_CHAIN_HEX}" }}] }});
            }} catch (switchError) {{
              console.warn("chain switch skipped", switchError);
            }}
            const accounts = await window.ethereum.request({{ method: "eth_requestAccounts" }});
            const wallet = accounts && accounts[0];
            const response = await fetch("/connect-wallet", {{
              method: "POST",
              headers: {{ "Content-Type": "application/json" }},
              body: JSON.stringify({{ wallet_address: wallet }})
            }});
            const payload = await response.json();
            if (!response.ok || !payload.ok) {{
              state.textContent = payload.error || "Unable to connect wallet.";
              return;
            }}
            state.textContent = `Wallet connected: ${{payload.wallet_address}} on Base Sepolia`;
          }});
        </script>
        """,
    )


@auth_bp.route("/api/auth/me", methods=["GET"])
def auth_me():
    if not current_user.is_authenticated:
        return jsonify({"ok": True, "authenticated": False, "user": None})
    return jsonify({"ok": True, "authenticated": True, "user": get_user_record(current_user.id)})


def founder_only_response() -> Response:
    if request.path.startswith("/api/") or request.accept_mimetypes.best == "application/json":
        return jsonify({"ok": False, "error": "Founder access required"}), 403
    abort(403)


def has_role(user: Any, roles: Iterable[str]) -> bool:
    allowed = {str(role).strip().lower() for role in roles if str(role).strip()}
    current_role = str(getattr(user, "role", "guest")).strip().lower()
    return current_role in allowed
