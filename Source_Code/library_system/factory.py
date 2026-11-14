"""Adapter selection at the application boundary."""

from __future__ import annotations

from .duckdb_repository import DuckDBRepository
from .sqlite_repository import SQLiteRepository
from .storage import Storage


def open_storage(engine: str, path: str) -> Storage:
    if engine == "sqlite":
        return SQLiteRepository(path)
    if engine == "duckdb":
        return DuckDBRepository(path)
    raise ValueError("Engine must be 'sqlite' or 'duckdb'.")
