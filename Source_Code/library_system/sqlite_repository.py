"""SQLite connector and transaction policy."""

from __future__ import annotations

import sqlite3

from .repository import SQLRepository


class SQLiteRepository(SQLRepository):
    begin_statement = "BEGIN IMMEDIATE"

    def __init__(self, path: str) -> None:
        connection = sqlite3.connect(path, timeout=5.0, isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        super().__init__(connection)
