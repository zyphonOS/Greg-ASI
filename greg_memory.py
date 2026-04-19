import sqlite3
import json
from datetime import datetime

DB_PATH = "greg_memory.db"

def init_memory_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS memories
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  intent_id TEXT,
                  description TEXT,
                  generated_code TEXT,
                  outcome TEXT,
                  reflection TEXT,
                  created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS reflections
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp TEXT,
                  drift_before REAL,
                  drift_after REAL,
                  reflection_text TEXT)''')
    conn.commit()
    conn.close()

def save_memory(intent_id, description, generated_code, outcome, reflection=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO memories (intent_id, description, generated_code, outcome, reflection, created_at) VALUES (?,?,?,?,?,?)",
              (intent_id, description, generated_code, outcome, reflection, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

def get_similar_memories(description, limit=3):
    # Simple keyword matching – upgrade to vector search later
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT description, generated_code, outcome FROM memories WHERE outcome='success' ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return [{"description": r[0], "code": r[1], "outcome": r[2]} for r in rows]

def log_reflection(drift_before, drift_after, reflection_text):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO reflections (timestamp, drift_before, drift_after, reflection_text) VALUES (?,?,?,?)",
              (datetime.utcnow().isoformat(), drift_before, drift_after, reflection_text))
    conn.commit()
    conn.close()