import sqlite3
import json
from datetime import datetime

DB_PATH = "intents.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS intents
                 (id TEXT PRIMARY KEY,
                  description TEXT,
                  status TEXT,
                  created_at TEXT,
                  updated_at TEXT,
                  result TEXT,
                  error TEXT)''')
    conn.commit()
    conn.close()

def save_intent(intent_id, description, status="pending"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    c.execute("INSERT OR REPLACE INTO intents (id, description, status, created_at, updated_at) VALUES (?,?,?,?,?)",
              (intent_id, description, status, now, now))
    conn.commit()
    conn.close()

def update_intent_status(intent_id, status, result=None, error=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    c.execute("UPDATE intents SET status=?, updated_at=?, result=?, error=? WHERE id=?",
              (status, now, result, error, intent_id))
    conn.commit()
    conn.close()

def get_intents(limit=50):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, description, status, created_at, updated_at, result, error FROM intents ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "description": r[1], "status": r[2], "created_at": r[3], "updated_at": r[4], "result": r[5], "error": r[6]} for r in rows]


def get_intent(intent_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT id, description, status, created_at, updated_at, result, error FROM intents WHERE id = ? LIMIT 1",
        (intent_id,),
    )
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0],
        "description": row[1],
        "status": row[2],
        "created_at": row[3],
        "updated_at": row[4],
        "result": row[5],
        "error": row[6],
    }
