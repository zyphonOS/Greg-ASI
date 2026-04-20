from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, render_template, request, stream_with_context
from flask_login import current_user, login_required

from core.utils import data_path, ensure_directory


CHAT_DB_PATH = data_path("chat_messages.db")
ROOMS = ("general", "tech", "random")
chat_bp = Blueprint("chat", __name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conn() -> sqlite3.Connection:
    ensure_directory(Path(CHAT_DB_PATH).parent)
    conn = sqlite3.connect(CHAT_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_chat_db() -> None:
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                user_email TEXT NOT NULL,
                room TEXT NOT NULL,
                dm_target_user_id INTEGER,
                message TEXT NOT NULL,
                response TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_room_id ON chat_messages(room, id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_user_id ON chat_messages(user_id, id)")


def _row_to_message(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "user_id": int(row["user_id"]),
        "user_email": str(row["user_email"]),
        "room": str(row["room"]),
        "dm_target_user_id": row["dm_target_user_id"],
        "message": str(row["message"]),
        "response": str(row["response"]),
        "timestamp": str(row["timestamp"]),
    }


def list_messages(room: str, *, limit: int = 40, since_id: int = 0) -> list[dict[str, Any]]:
    clean_room = room if room in ROOMS else "general"
    with _conn() as conn:
        if since_id > 0:
            rows = conn.execute(
                """
                SELECT *
                FROM chat_messages
                WHERE room = ? AND id > ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (clean_room, since_id, int(limit)),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT *
                FROM chat_messages
                WHERE room = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (clean_room, int(limit)),
            ).fetchall()
            rows = list(reversed(rows))
    return [_row_to_message(row) for row in rows]


def save_message(*, user_id: int, user_email: str, room: str, message: str, response: str) -> dict[str, Any]:
    clean_room = room if room in ROOMS else "general"
    with _conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO chat_messages (user_id, user_email, room, dm_target_user_id, message, response, timestamp)
            VALUES (?, ?, ?, NULL, ?, ?, ?)
            """,
            (int(user_id), str(user_email), clean_room, str(message), str(response), _utc_now()),
        )
        row_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM chat_messages WHERE id = ?", (row_id,)).fetchone()
    if not row:
        raise RuntimeError("Unable to reload saved chat message.")
    return _row_to_message(row)


def _greg_mode_for_room(room: str) -> str:
    return {
        "general": "presence",
        "tech": "devschool",
        "random": "studio",
    }.get(room, "presence")


def _chat_prompt(room: str, message: str) -> str:
    return f"Room: {room}. User says: {message}"


@chat_bp.route("/chat")
@login_required
def chat():
    current_room = str(request.args.get("room") or "general").strip().lower()
    if current_room not in ROOMS:
        current_room = "general"
    return render_template(
        "chat.html",
        rooms=ROOMS,
        current_room=current_room,
        chat_user={"email": current_user.email, "role": current_user.role},
    )


@chat_bp.route("/api/chat/history", methods=["GET"])
@login_required
def api_chat_history():
    room = str(request.args.get("room") or "general").strip().lower()
    return jsonify({"ok": True, "messages": list_messages(room, limit=60)})


@chat_bp.route("/api/chat/send", methods=["POST"])
@login_required
def api_chat_send():
    payload = request.get_json(silent=True) or {}
    room = str(payload.get("room") or "general").strip().lower()
    message = str(payload.get("message") or "").strip()
    if room not in ROOMS:
        return jsonify({"ok": False, "error": "Invalid room"}), 400
    if not message:
        return jsonify({"ok": False, "error": "message is required"}), 400

    command_locus = current_app.extensions.get("command_locus")
    if command_locus is None:
        return jsonify({"ok": False, "error": "Greg command locus is unavailable"}), 500

    greg_payload, status_code = command_locus.dispatch(
        "think",
        {
            "prompt": _chat_prompt(room, message),
            "user_id": f"chat-user-{current_user.id}",
            "mode": _greg_mode_for_room(room),
        },
    )
    if status_code >= 400 or not greg_payload.get("ok"):
        return jsonify({"ok": False, "error": greg_payload.get("error") or "Greg did not respond"}), 500

    saved = save_message(
        user_id=int(current_user.id),
        user_email=current_user.email,
        room=room,
        message=message,
        response=str(greg_payload.get("response") or ""),
    )
    return jsonify({"ok": True, "entry": saved, "tick": greg_payload.get("tick", 0)})


@chat_bp.route("/api/chat/stream", methods=["GET"])
@login_required
def api_chat_stream():
    room = str(request.args.get("room") or "general").strip().lower()
    last_id = int(request.args.get("last_id") or 0)
    if room not in ROOMS:
        return jsonify({"ok": False, "error": "Invalid room"}), 400

    @stream_with_context
    def generate():
        cursor = last_id
        while True:
            rows = list_messages(room, since_id=cursor, limit=50)
            for row in rows:
                cursor = max(cursor, int(row["id"]))
                yield f"data: {json.dumps(row, ensure_ascii=True)}\n\n"
            yield ": keep-alive\n\n"
            time.sleep(1.0)

    return Response(generate(), mimetype="text/event-stream")
