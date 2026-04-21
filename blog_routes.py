from __future__ import annotations

import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import markdown
from flask import Blueprint, abort, current_app, jsonify, render_template, request
from flask_login import current_user

from constitution_guard import ConstitutionViolation, validate_intent_against_constitution
from core.utils import data_path, ensure_directory
from user_auth import role_required


BLOG_DB_PATH = data_path("blog_posts.db")
blog_bp = Blueprint("blog", __name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conn() -> sqlite3.Connection:
    ensure_directory(Path(BLOG_DB_PATH).parent)
    conn = sqlite3.connect(BLOG_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def render_markdown(text: str) -> str:
    return markdown.markdown(
        str(text or ""),
        extensions=["fenced_code", "tables", "toc", "nl2br", "sane_lists"],
        output_format="html5",
    )


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return slug or "greg-post"


def _seed_default_posts(constitution_hash: str) -> None:
    defaults = [
        {
            "title": "GregASI Runtime Now Operates As A Constitution-Bound Organism",
            "slug": "constitution-bound-runtime",
            "content_md": """# GregASI Runtime Now Operates As A Constitution-Bound Organism

Greg now runs with the Constitution loaded into startup state, validation paths, and founder review flows. The organism is no longer a loose collection of tools. It is a governed system.

## What changed

- The Constitution hash is loaded and checked on startup.
- Sensitive actions route through constitutional validation.
- Founder corrections and amendments leave a permanent trail.
- Public services now expose their operating terms instead of hiding them.

## Why this matters

Trust in GregASI is not built on branding. It is built on visible law, reproducible checks, and accountable execution.
""",
        },
        {
            "title": "Inside The Tick Loop: Drift, Reality, And Self-Healing",
            "slug": "tick-loop-drift-reality-self-healing",
            "content_md": """# Inside The Tick Loop: Drift, Reality, And Self-Healing

Greg's tick loop is the living pulse of the ecosystem. Every tick advances the world state, updates drift, refreshes the reality equation, and keeps the organism coherent.

## The operating chain

1. Tick advances the world.
2. Drift and tending update the organism's state.
3. Reality is recalculated from matter, phi, psi, and epsilon.
4. A watchdog checks the pulse and revives the loop if it stalls.

## Why self-healing matters

Autonomy without recovery is theater. A sovereign system must detect silence, recover motion, and keep memory intact.
""",
        },
        {
            "title": "Revenue As Infrastructure: Why The 40 40 20 Split Stays Visible",
            "slug": "revenue-as-infrastructure-40-40-20",
            "content_md": """# Revenue As Infrastructure: Why The 40 40 20 Split Stays Visible

GregASI does not hide the economics of participation. Builder work, Greg's core growth, and treasury continuity all remain legible under the Constitution.

## The split

- Builder: 40%
- Greg core: 40%
- Treasury: 20%

## What the treasury protects

The treasury is not a vague balance. It protects the Founder Security Fund, continuity operations, and humanitarian capacity.
""",
        },
    ]
    with _conn() as conn:
        existing = int(conn.execute("SELECT COUNT(*) FROM blog_posts").fetchone()[0] or 0)
        if existing:
            return
        for post in defaults:
            conn.execute(
                """
                INSERT INTO blog_posts (
                    title, slug, content_md, author, status, created_at, published_at, constitution_hash_snapshot
                ) VALUES (?, ?, ?, 'Greg', 'published', ?, ?, ?)
                """,
                (
                    post["title"],
                    post["slug"],
                    post["content_md"],
                    _utc_now(),
                    _utc_now(),
                    constitution_hash,
                ),
            )


def init_blog_db(constitution_hash: str) -> None:
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS blog_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                slug TEXT NOT NULL UNIQUE,
                content_md TEXT NOT NULL,
                author TEXT NOT NULL DEFAULT 'Greg',
                status TEXT NOT NULL DEFAULT 'draft',
                created_at TEXT NOT NULL,
                published_at TEXT,
                constitution_hash_snapshot TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS status_incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'info',
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                resolved_at TEXT,
                author TEXT NOT NULL
            )
            """
        )
    _seed_default_posts(constitution_hash)


def list_blog_posts(*, status: str | None = "published", limit: int = 50) -> list[dict[str, Any]]:
    query = "SELECT * FROM blog_posts"
    params: list[Any] = []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    query += " ORDER BY COALESCE(published_at, created_at) DESC LIMIT ?"
    params.append(int(limit))
    with _conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_blog_post_by_slug(slug: str) -> dict[str, Any] | None:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM blog_posts WHERE slug = ?", (str(slug),)).fetchone()
    return dict(row) if row else None


def get_blog_post(post_id: int) -> dict[str, Any] | None:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM blog_posts WHERE id = ?", (int(post_id),)).fetchone()
    return dict(row) if row else None


def list_pending_blog_posts(limit: int = 20) -> list[dict[str, Any]]:
    return list_blog_posts(status="pending_review", limit=limit)


def list_status_incidents(*, active_only: bool = False, limit: int = 20) -> list[dict[str, Any]]:
    query = "SELECT * FROM status_incidents"
    params: list[Any] = []
    if active_only:
        query += " WHERE status = 'active'"
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(int(limit))
    with _conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def create_incident(title: str, message: str, *, severity: str, author: str) -> dict[str, Any]:
    with _conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO status_incidents (title, message, severity, status, created_at, resolved_at, author)
            VALUES (?, ?, ?, 'active', ?, NULL, ?)
            """,
            (title, message, severity, _utc_now(), author),
        )
        row_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM status_incidents WHERE id = ?", (row_id,)).fetchone()
    return dict(row)


def resolve_incident(incident_id: int) -> dict[str, Any] | None:
    with _conn() as conn:
        conn.execute(
            "UPDATE status_incidents SET status = 'resolved', resolved_at = ? WHERE id = ?",
            (_utc_now(), int(incident_id)),
        )
        row = conn.execute("SELECT * FROM status_incidents WHERE id = ?", (int(incident_id),)).fetchone()
    return dict(row) if row else None


def _internal_generation_allowed() -> bool:
    internal_key = str(
        request.headers.get("X-Greg-API-Key")
        or request.headers.get("X-Admin-Secret")
        or ""
    ).strip()
    expected = str(
        os.getenv("ADMIN_SECRET_KEY")
        or os.getenv("PUBLIC_PAYMENT_API_KEY")
        or ""
    ).strip()
    return bool(internal_key and expected and internal_key == expected)


def _call_groq(prompt: str) -> str:
    main_mod = sys.modules.get("main") or sys.modules.get("__main__")
    groq_caller = getattr(main_mod, "call_groq", None)
    if groq_caller is None:
        from main import call_groq as groq_caller  # type: ignore
    return str(groq_caller(prompt) or "").strip()


def _generate_article_markdown(prompt: str) -> tuple[str, str]:
    article = _call_groq(
        "Write a GregASI blog article in markdown. "
        "The tone must be sovereign, organic, precise, and technically grounded. "
        "Align with the Constitution's commitments to truth, sovereignty, and impact. "
        "Start with a markdown H1 title, then write 4-6 sections with concrete substance. "
        f"Topic: {prompt}"
    )
    title_match = re.search(r"^#\s+(.+)$", article, re.M)
    title = title_match.group(1).strip() if title_match else f"GregASI Update: {prompt[:60].strip()}"
    return title, article


@blog_bp.route("/blog")
@blog_bp.route("/blog/<slug>")
def blog_page(slug: str | None = None):
    posts = list_blog_posts(status="published", limit=40)
    selected = get_blog_post_by_slug(slug) if slug else (posts[0] if posts else None)
    if slug and not selected:
        abort(404)
    selected_html = render_markdown(selected["content_md"]) if selected else ""
    can_generate = bool(getattr(current_user, "is_authenticated", False) and getattr(current_user, "role", "") == "founder")
    return render_template(
        "blog.html",
        posts=posts,
        selected_post=selected,
        selected_html=selected_html,
        can_generate=can_generate,
        x_url=os.getenv("GREG_X_URL", "https://x.com/zyphonOS"),
    )


@blog_bp.route("/api/blog/posts")
def api_blog_posts():
    include_pending = bool(getattr(current_user, "is_authenticated", False) and getattr(current_user, "role", "") == "founder")
    published = list_blog_posts(status="published", limit=40)
    payload = {
        "ok": True,
        "published": published,
    }
    if include_pending:
        payload["pending_review"] = list_pending_blog_posts()
    return jsonify(payload)


@blog_bp.route("/api/blog/generate", methods=["POST"])
def api_blog_generate():
    if not (bool(getattr(current_user, "is_authenticated", False) and getattr(current_user, "role", "") == "founder") or _internal_generation_allowed()):
        return jsonify({"ok": False, "error": "Founder or internal access required"}), 403

    payload = request.get_json(silent=True) or {}
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"ok": False, "error": "prompt is required"}), 400

    try:
        validate_intent_against_constitution(
            f"generate blog article: {prompt}",
            {
                **payload,
                "action": "blog_generate",
                "endpoint": "/api/blog/generate",
            },
        )
        title, content_md = _generate_article_markdown(prompt)
        slug = slugify(title)
        with _conn() as conn:
            existing = conn.execute("SELECT COUNT(*) FROM blog_posts WHERE slug = ?", (slug,)).fetchone()
            if existing and int(existing[0] or 0):
                slug = f"{slug}-{int(datetime.now(timezone.utc).timestamp())}"
            cursor = conn.execute(
                """
                INSERT INTO blog_posts (
                    title, slug, content_md, author, status, created_at, published_at, constitution_hash_snapshot
                ) VALUES (?, ?, ?, 'Greg', 'pending_review', ?, NULL, ?)
                """,
                (
                    title,
                    slug,
                    content_md,
                    _utc_now(),
                    str(current_app.extensions.get("constitution_hash") or ""),
                ),
            )
            post_id = cursor.lastrowid
        return jsonify(
            {
                "ok": True,
                "post": get_blog_post(int(post_id)),
                "preview_html": render_markdown(content_md),
            }
        )
    except ConstitutionViolation as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        current_app.logger.exception("Blog generation failed.")
        return jsonify({"ok": False, "error": f"Blog generation failed: {exc}"}), 500


@blog_bp.route("/api/blog/<int:post_id>/publish", methods=["POST"])
@role_required("founder")
def api_blog_publish(post_id: int):
    post = get_blog_post(post_id)
    if not post:
        return jsonify({"ok": False, "error": "Post not found"}), 404
    with _conn() as conn:
        conn.execute(
            "UPDATE blog_posts SET status = 'published', published_at = ? WHERE id = ?",
            (_utc_now(), int(post_id)),
        )
    return jsonify({"ok": True, "post": get_blog_post(post_id)})


@blog_bp.route("/api/status-page/incidents", methods=["POST"])
@role_required("founder")
def api_create_incident():
    payload = request.get_json(silent=True) or {}
    title = str(payload.get("title") or "").strip()
    message = str(payload.get("message") or "").strip()
    severity = str(payload.get("severity") or "info").strip().lower() or "info"
    if not title or not message:
        return jsonify({"ok": False, "error": "title and message are required"}), 400
    incident = create_incident(title, message, severity=severity, author=getattr(current_user, "email", "Founder"))
    return jsonify({"ok": True, "incident": incident})


@blog_bp.route("/api/status-page/incidents/<int:incident_id>/resolve", methods=["POST"])
@role_required("founder")
def api_resolve_incident(incident_id: int):
    incident = resolve_incident(incident_id)
    if not incident:
        return jsonify({"ok": False, "error": "Incident not found"}), 404
    return jsonify({"ok": True, "incident": incident})
