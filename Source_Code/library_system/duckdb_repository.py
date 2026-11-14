"""DuckDB connector and transaction policy (optional runtime dependency)."""

from __future__ import annotations

from contextlib import contextmanager
from threading import RLock

from .repository import SQLRepository


class DuckDBRepository(SQLRepository):
    begin_statement = "BEGIN TRANSACTION"
    _write_lock = RLock()

    def __init__(self, path: str) -> None:
        try:
            import duckdb
        except ImportError as exc:
            raise RuntimeError("Install project dependencies with: pip install -r requirements.txt") from exc
        super().__init__(duckdb.connect(path))

    @contextmanager
    def transaction(self):
        """Serialize write transactions across this process's DuckDB connections."""
        with self._write_lock:
            with super().transaction():
                yield
