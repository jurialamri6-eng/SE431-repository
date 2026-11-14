"""DuckDB connector and transaction policy (optional runtime dependency)."""

from __future__ import annotations

from .repository import SQLRepository


class DuckDBRepository(SQLRepository):
    begin_statement = "BEGIN TRANSACTION"

    def __init__(self, path: str) -> None:
        try:
            import duckdb
        except ImportError as exc:
            raise RuntimeError("Install project dependencies with: pip install -r requirements.txt") from exc
        super().__init__(duckdb.connect(path))
