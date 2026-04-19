from __future__ import annotations

from core.memory import SQLiteMemory, get_sqlite_memory


class LocalMemory(SQLiteMemory):
    pass


def get_local_memory() -> SQLiteMemory:
    return get_sqlite_memory()
