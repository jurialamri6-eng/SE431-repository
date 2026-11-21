from __future__ import annotations

import contextlib
import csv
import io
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from library_system.factory import open_storage
from library_system.migration import migrate_legacy_sqlite
from library_system.models import BorrowableItem, ItemType, LoanPolicy, Member
from library_system.service import LendingService


class CirculationTestMixin:
    engine: str

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.database = str(Path(self.temp.name) / f"refactored.{self.engine}.db")
        self.storage = open_storage(self.engine, self.database)
        self.storage.create_schema()
        with self.storage.transaction():
            self.storage.add_member(Member("S1", "Ali", "ACTIVE"))
            self.storage.add_member(Member("S2", "Sara", "ACTIVE"))
            self.storage.add_member(Member("INACTIVE", "Inactive", "INACTIVE"))
            self.storage.add_item(
                BorrowableItem(1, ItemType.BOOK, "Clean Code", "Robert Martin", 2, 2)
            )
            self.storage.add_item(
                BorrowableItem(2, ItemType.BOOK, "Refactoring", "Martin Fowler", 2, 2)
            )
            self.storage.add_item(
                BorrowableItem(3, ItemType.BOOK, "Design Patterns", "Gamma et al.", 1, 1)
            )
        self.now = datetime(2026, 11, 1, 10, 0)
        self.service = LendingService(
            self.storage, {ItemType.BOOK: LoanPolicy()}, clock=lambda: self.now
        )

    def tearDown(self) -> None:
        self.storage.close()
        self.temp.cleanup()

    def test_multiple_copies_exhaustion_and_atomic_return(self) -> None:
        first = self.service.borrow("S1", ItemType.BOOK, 1)
        second = self.service.borrow("S2", ItemType.BOOK, 1)
        rejected = self.service.borrow("S1", ItemType.BOOK, 1)
        self.assertTrue(first.success)
        self.assertTrue(second.success)
        self.assertFalse(rejected.success)
        self.assertEqual(self.storage.get_item(ItemType.BOOK, 1).available_copies, 0)
        outcome = self.service.return_item("S1", ItemType.BOOK, 1, first.loan.loan_id)
        duplicate = self.service.return_item("S1", ItemType.BOOK, 1, first.loan.loan_id)
        self.assertTrue(outcome.success)
        self.assertFalse(duplicate.success)
        self.assertEqual(self.storage.get_item(ItemType.BOOK, 1).available_copies, 1)

    def test_member_limit_and_member_status(self) -> None:
        self.assertFalse(self.service.borrow("MISSING", ItemType.BOOK, 1).success)
        self.assertFalse(self.service.borrow("INACTIVE", ItemType.BOOK, 1).success)
        self.assertTrue(self.service.borrow("S1", ItemType.BOOK, 1).success)
        self.assertTrue(self.service.borrow("S1", ItemType.BOOK, 1).success)
        self.assertTrue(self.service.borrow("S1", ItemType.BOOK, 2).success)
        rejected = self.service.borrow("S1", ItemType.BOOK, 3)
        self.assertEqual(rejected.message, "Borrowing limit reached")
        self.assertEqual(self.storage.count_open_loans("S1"), 3)

    def test_multiple_same_title_requires_specific_loan_id(self) -> None:
        first = self.service.borrow("S1", ItemType.BOOK, 1)
        second = self.service.borrow("S1", ItemType.BOOK, 1)
        ambiguous = self.service.return_item("S1", ItemType.BOOK, 1)
        self.assertTrue(first.success and second.success)
        self.assertFalse(ambiguous.success)
        self.assertEqual(len(self.service.list_open_loans("S1", ItemType.BOOK, 1)), 2)
        self.assertTrue(
            self.service.return_item("S1", ItemType.BOOK, 1, second.loan.loan_id).success
        )
        self.assertEqual(self.storage.get_item(ItemType.BOOK, 1).available_copies, 1)

    def test_fourteen_day_due_date_and_fine_day_rounding(self) -> None:
        one_hour = self.service.borrow("S1", ItemType.BOOK, 3)
        self.assertEqual(one_hour.loan.due_at, self.now + timedelta(days=14))
        returned = self.service.return_item(
            "S1", ItemType.BOOK, 3, one_hour.loan.loan_id
        )
        self.assertTrue(returned.success)
        self.assertEqual(returned.fine, 0)

        another = self.service.borrow("S1", ItemType.BOOK, 3)
        self.now = another.loan.due_at + timedelta(hours=25)
        late = self.service.return_item("S1", ItemType.BOOK, 3, another.loan.loan_id)
        self.assertEqual(late.fine, 1)

    def test_search_preserves_case_insensitive_and_sql_wildcards(self) -> None:
        self.assertEqual(
            [item.item_id for item in self.service.search("cLeAn")], [1]
        )
        self.assertEqual(
            [item.item_id for item in self.service.search("Clean_Code", ItemType.BOOK)], [1]
        )
        self.assertEqual(len(self.service.search("%", ItemType.BOOK)), 3)

    def test_accented_search_matches_legacy_sqlite(self) -> None:
        with self.storage.transaction():
            self.storage.add_item(BorrowableItem(4, ItemType.BOOK, "École", "Demo", 1, 1))
            self.storage.add_item(BorrowableItem(5, ItemType.BOOK, "Textbook", "Élodie", 1, 1))

        for query, expected_ids in (
            ("école", []),
            ("École", [4]),
            ("ÉCO_E", [4]),
            ("E\u0301cole", []),
            ("élodie", []),
            ("ÉLODIE", [5]),
            ("École\x00ignored", [4]),
            ("", [1, 2, 3, 4, 5]),
        ):
            with self.subTest(query=query):
                self.assertEqual(
                    [item.item_id for item in self.service.search(query, ItemType.BOOK)],
                    expected_ids,
                )

    def test_returned_loan_agrees_with_database_and_restores_stock_once(self) -> None:
        first = self.service.borrow("S1", ItemType.BOOK, 1)
        second = self.service.borrow("S1", ItemType.BOOK, 1)
        self.assertTrue(first.success and second.success)
        self.assertFalse(first.loan.returned)
        loan_id = first.loan.loan_id
        self.now = first.loan.due_at + timedelta(hours=25)

        with patch.object(self.storage, "increase_available", side_effect=RuntimeError("forced return failure")):
            with self.assertRaisesRegex(RuntimeError, "forced return failure"):
                self.service.return_item("S1", ItemType.BOOK, 1, loan_id)
        self.assertIsNotNone(self.storage.get_open_loan(loan_id))
        self.assertEqual(self.storage.get_item(ItemType.BOOK, 1).available_copies, 0)

        result = self.service.return_item("S1", ItemType.BOOK, 1, loan_id)
        self.assertTrue(result.success)
        self.assertEqual(result.fine, 1)
        self.assertEqual(result.loan.loan_id, loan_id)
        self.assertIs(result.loan.returned, True)
        saved = self.storage.connection.execute(
            "SELECT returned FROM loans WHERE id = ?", (loan_id,)
        ).fetchone()
        self.assertEqual(saved, (int(result.loan.returned),))

        duplicate = self.service.return_item("S1", ItemType.BOOK, 1, loan_id)
        self.assertFalse(duplicate.success)
        self.assertIsNone(duplicate.loan)
        self.assertEqual(self.storage.get_item(ItemType.BOOK, 1).available_copies, 1)
        self.assertIsNotNone(self.storage.get_open_loan(second.loan.loan_id))

    def test_failed_copy_update_rolls_back_loan_and_stock(self) -> None:
        with patch.object(self.storage, "decrease_available", side_effect=RuntimeError("forced")):
            with self.assertRaisesRegex(RuntimeError, "forced"):
                self.service.borrow("S1", ItemType.BOOK, 1)
        self.assertEqual(self.storage.count_open_loans("S1"), 0)
        self.assertEqual(self.storage.get_item(ItemType.BOOK, 1).available_copies, 2)


class SQLiteCirculationTests(CirculationTestMixin, unittest.TestCase):
    engine = "sqlite"


class DuckDBCirculationTests(CirculationTestMixin, unittest.TestCase):
    engine = "duckdb"


class ReengineeredMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "legacy.sqlite3"
        self.target = self.root / "migrated.duckdb"
        connection = sqlite3.connect(self.source)
        connection.executescript(
            """
            CREATE TABLE members(id TEXT PRIMARY KEY, name TEXT, status TEXT);
            CREATE TABLE books(id INTEGER PRIMARY KEY, title TEXT, author TEXT, available INTEGER);
            CREATE TABLE loans(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                member_id TEXT, book_id INTEGER, borrow_date TEXT, due_date TEXT, returned INTEGER
            );
            INSERT INTO members VALUES ('S1', 'Ali', 'ACTIVE');
            INSERT INTO books VALUES (8, 'Before Refactoring', 'A. Writer', 0);
            INSERT INTO loans VALUES (41, 'S1', 8, '2026-10-01T10:00:00', '2026-10-15T10:00:00', 0);
            """
        )
        connection.close()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_data_and_ids_are_preserved_in_alternate_engine(self) -> None:
        inventory = self.root / "inventory.csv"
        with inventory.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=("book_id", "total_copies"))
            writer.writeheader()
            writer.writerow({"book_id": 8, "total_copies": 3})
        result = migrate_legacy_sqlite(self.source, self.target, "duckdb", inventory)
        self.assertEqual(result, {"members": 1, "items": 1, "loans": 1})
        target = open_storage("duckdb", str(self.target))
        try:
            item = target.get_item(ItemType.BOOK, 8)
            loan = target.get_open_loan(41)
            self.assertEqual((item.total_copies, item.available_copies), (3, 2))
            self.assertEqual((loan.loan_id, loan.item_id, loan.returned), (41, 8, False))
        finally:
            target.close()
        source = sqlite3.connect(self.source)
        try:
            self.assertEqual(source.execute("SELECT available FROM books WHERE id=8").fetchone(), (0,))
        finally:
            source.close()


if __name__ == "__main__":
    unittest.main()
