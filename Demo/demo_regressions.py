"""Show the review regressions on SQLite and DuckDB using temporary databases."""

from __future__ import annotations

import argparse
import contextlib
import io
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Source_Code"))

from legacy.legacy_system_executable import search_books
from library_system.factory import open_storage
from library_system.models import BorrowableItem, ItemType, LoanPolicy, Member
from library_system.service import LendingService


def original_matches(query: str) -> list[str]:
    with contextlib.closing(sqlite3.connect(":memory:")) as database:
        database.execute("CREATE TABLE books(id, title, author, available)")
        database.execute("INSERT INTO books VALUES (1, 'École', 'Demo Author', 1)")
        with contextlib.redirect_stdout(io.StringIO()):
            return [row[1] for row in search_books(database, query)]


def check_engine(engine: str, expect_baseline: bool, folder: Path) -> None:
    storage = open_storage(engine, str(folder / f"regressions.{engine}"))
    with contextlib.closing(storage):
        storage.create_schema()
        with storage.transaction():
            storage.add_member(Member("S1", "Demo member", "ACTIVE"))
            storage.add_item(BorrowableItem(1, ItemType.BOOK, "École", "Demo Author", 2, 2))

        clock = datetime(2026, 11, 1, 10)
        service = LendingService(storage, {ItemType.BOOK: LoanPolicy()}, clock=lambda: clock)
        queries = ("école", "École", "ÉCO_E", "dEmO aUtHoR", "%", "")
        print(f"{engine.upper()}  |  Temporary sample database")
        for query in queries:
            actual = [item.name for item in service.search(query, ItemType.BOOK)]
            expected = original_matches(query)
            print(f"  search {query!r}: {actual}  |  original SQLite: {expected}")
            if expect_baseline and engine == "duckdb" and query == "école":
                assert actual == ["École"] and expected == []
            else:
                assert actual == expected, (engine, query, actual, expected)

        borrowed = service.borrow("S1", ItemType.BOOK, 1)
        assert borrowed.success and borrowed.loan is not None
        assert borrowed.loan.due_at == clock + timedelta(days=14)
        clock = borrowed.loan.due_at + timedelta(hours=25)
        returned = service.return_item("S1", ItemType.BOOK, 1, borrowed.loan.loan_id)
        assert returned.success and returned.loan is not None
        saved = storage.connection.execute(
            "SELECT returned FROM loans WHERE id = ?", (borrowed.loan.loan_id,)
        ).fetchone()[0]
        print(f"  returned in the result: {returned.loan.returned}  |  stored returned: {bool(saved)}")
        print(f"  fine for 25 hours overdue: {returned.fine}")
        assert bool(saved) is True and returned.loan.returned is not expect_baseline
        assert returned.fine == 1

        stock = storage.get_item(ItemType.BOOK, 1).available_copies
        duplicate = service.return_item("S1", ItemType.BOOK, 1, borrowed.loan.loan_id)
        stock_after = storage.get_item(ItemType.BOOK, 1).available_copies
        print(f"  repeat accepted: {duplicate.success}  |  available before and after: {stock}/{stock_after}")
        assert not duplicate.success and stock == stock_after == 2


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expect-baseline", action="store_true", help="Reproduce the reported defects")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="se431-regressions-") as path:
        for engine in ("sqlite", "duckdb"):
            check_engine(engine, args.expect_baseline, Path(path))
    print("\nBaseline defects reproduced." if args.expect_baseline else "\nAll direct correction checks passed.")


if __name__ == "__main__":
    main()
