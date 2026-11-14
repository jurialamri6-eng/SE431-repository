from __future__ import annotations

import contextlib
import csv
import io
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import pre_refactor_system as app


ENGINES = ("sqlite", "duckdb")


class EngineBehaviourMixin:
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / f"library.{self.engine}.db"
        self.connection = app.open_database(self.engine, self.database)
        app.initialize_schema(self.connection, self.engine)

    def tearDown(self) -> None:
        self.connection.close()
        self.temp.cleanup()

    def test_multiple_copies_and_last_copy_rejection(self) -> None:
        now = datetime(2026, 11, 1, 10, 0)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertTrue(app.borrow(self.connection, self.engine, "S1", 1, now=now))
            self.assertTrue(app.borrow(self.connection, self.engine, "S2", 1, now=now))
            self.assertFalse(app.borrow(self.connection, self.engine, "S1", 1, now=now))
        stock = self.connection.execute(
            "SELECT available_copies, total_copies FROM items WHERE item_type='BOOK' AND item_id=1"
        ).fetchone()
        self.assertEqual(stock, (0, 2))
        self.assertIn("Book is unavailable", output.getvalue())

    def test_three_outstanding_loan_limit(self) -> None:
        now = datetime(2026, 11, 1, 10, 0)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(app.borrow(self.connection, self.engine, "S1", 1, now=now))
            self.assertTrue(app.borrow(self.connection, self.engine, "S1", 1, now=now))
            self.assertTrue(app.borrow(self.connection, self.engine, "S1", 2, now=now))
            self.assertFalse(app.borrow(self.connection, self.engine, "S1", 3, now=now))
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM loans WHERE member_id='S1' AND returned=0"
            ).fetchone()[0],
            3,
        )

    def test_return_restores_one_copy_and_cannot_repeat(self) -> None:
        now = datetime(2026, 11, 1, 10, 0)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(app.borrow(self.connection, self.engine, "S1", 1, now=now))
        loan_id = app.list_open_loans(self.connection, "S1", 1)[0][0]
        with contextlib.redirect_stdout(io.StringIO()):
            fine = app.return_book(
                self.connection, self.engine, "S1", 1, loan_id, now=now + timedelta(days=14, hours=25)
            )
            duplicate = app.return_book(
                self.connection, self.engine, "S1", 1, loan_id, now=now + timedelta(days=15)
            )
        self.assertEqual(fine, 1)
        self.assertIsNone(duplicate)
        self.assertEqual(
            self.connection.execute(
                "SELECT available_copies FROM items WHERE item_type='BOOK' AND item_id=1"
            ).fetchone()[0],
            2,
        )

    def test_search_keeps_wildcard_and_case_insensitive_matching(self) -> None:
        rows = app.search_books(self.connection, "cLeAn")
        self.assertEqual([row[0] for row in rows], [1])
        all_rows = app.search_books(self.connection, "%")
        self.assertEqual(len(all_rows), 3)

class SQLiteBehaviourTests(EngineBehaviourMixin, unittest.TestCase):
    engine = "sqlite"


class DuckDBBehaviourTests(EngineBehaviourMixin, unittest.TestCase):
    engine = "duckdb"


class MigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "legacy.sqlite3"
        self.destination = self.root / "reengineered.duckdb"
        db = sqlite3.connect(self.source)
        db.executescript(
            """
            CREATE TABLE members(id TEXT PRIMARY KEY, name TEXT, status TEXT);
            CREATE TABLE books(id INTEGER PRIMARY KEY, title TEXT, author TEXT, available INTEGER);
            CREATE TABLE loans(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                member_id TEXT, book_id INTEGER, borrow_date TEXT, due_date TEXT, returned INTEGER
            );
            INSERT INTO members VALUES ('S1', 'Ali', 'ACTIVE');
            INSERT INTO books VALUES (7, 'Legacy Book', 'A. Writer', 0);
            INSERT INTO loans VALUES (19, 'S1', 7, '2026-10-01T10:00:00', '2026-10-15T10:00:00', 0);
            """
        )
        db.close()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_migration_to_duckdb_preserves_ids_and_uses_verified_inventory(self) -> None:
        inventory = self.root / "inventory.csv"
        with inventory.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=("book_id", "total_copies"))
            writer.writeheader()
            writer.writerow({"book_id": 7, "total_copies": 3})
        result = app.migrate_legacy_sqlite(self.source, self.destination, "duckdb", inventory)
        self.assertEqual(result, {"members": 1, "items": 1, "loans": 1})
        new_db = app.open_database("duckdb", self.destination)
        try:
            self.assertEqual(
                new_db.execute(
                    "SELECT item_id, total_copies, available_copies FROM items"
                ).fetchone(),
                (7, 3, 2),
            )
            self.assertEqual(
                new_db.execute("SELECT id, item_type, item_id FROM loans").fetchone(),
                (19, "BOOK", 7),
            )
        finally:
            new_db.close()
        unchanged = sqlite3.connect(self.source)
        try:
            self.assertEqual(unchanged.execute("SELECT available FROM books").fetchone(), (0,))
        finally:
            unchanged.close()

    def test_ambiguous_legacy_availability_requires_inventory(self) -> None:
        db = sqlite3.connect(self.source)
        db.execute("UPDATE books SET available=0 WHERE id=7")
        db.execute("DELETE FROM loans")
        db.commit()
        db.close()
        with self.assertRaisesRegex(ValueError, "ambiguous legacy stock"):
            app.migrate_legacy_sqlite(self.source, self.destination, "duckdb")


if __name__ == "__main__":
    unittest.main()
