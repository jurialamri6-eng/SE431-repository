from __future__ import annotations

import contextlib
import io
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from legacy import legacy_system_executable as legacy
from library_system.factory import open_storage
from library_system.models import BorrowableItem, ItemType, LoanPolicy, Member
from library_system.service import LendingService


class FrozenDateTime(datetime):
    value = datetime(2026, 11, 1, 10, 0)

    @classmethod
    def now(cls, tz=None):
        return cls.value


class LegacyCompatibilityTests(unittest.TestCase):
    def test_single_copy_borrow_search_due_date_and_fine_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "legacy.sqlite3"
            target_path = Path(directory) / "refactored.sqlite3"
            original_db = legacy.DB
            legacy.DB = str(source_path)
            self.addCleanup(setattr, legacy, "DB", original_db)
            self.addCleanup(
                setattr, FrozenDateTime, "value", datetime(2026, 11, 1, 10, 0)
            )
            with contextlib.ExitStack() as stack:
                stack.enter_context(patch.object(legacy, "datetime", FrozenDateTime))
                source = legacy.setup()
                target = open_storage("sqlite", str(target_path))
                target.create_schema()
                with target.transaction():
                    for member_id, name, status in source.execute(
                        "SELECT id, name, status FROM members"
                    ).fetchall():
                        target.add_member(Member(member_id, name, status))
                    for item_id, title, author, available in source.execute(
                        "SELECT id, title, author, available FROM books"
                    ).fetchall():
                        target.add_item(
                            BorrowableItem(
                                item_id, ItemType.BOOK, title, author,
                                total_copies=1, available_copies=available,
                            )
                        )
                service = LendingService(
                    target,
                    {ItemType.BOOK: LoanPolicy()},
                    clock=lambda: FrozenDateTime.value,
                )

                with contextlib.redirect_stdout(io.StringIO()):
                    old_search = legacy.search_books(source, "cLeAn")
                new_search = service.search("cLeAn", ItemType.BOOK)
                self.assertEqual(
                    [(row[0], row[1], row[2], row[3]) for row in old_search],
                    [
                        (item.item_id, item.name, item.creator, item.available_copies)
                        for item in new_search
                    ],
                )

                with contextlib.redirect_stdout(io.StringIO()):
                    old_success = legacy.borrow(source, "S1", 1)
                new_result = service.borrow("S1", ItemType.BOOK, 1)
                self.assertEqual(old_success, new_result.success)
                self.assertEqual(new_result.loan.due_at, FrozenDateTime.value + timedelta(days=14))
                self.assertEqual(
                    source.execute("SELECT available FROM books WHERE id=1").fetchone()[0],
                    target.get_item(ItemType.BOOK, 1).available_copies,
                )

                FrozenDateTime.value = new_result.loan.due_at + timedelta(hours=25)
                with contextlib.redirect_stdout(io.StringIO()) as old_output:
                    old_return = legacy.return_book(source, "S1", 1)
                new_return = service.return_item(
                    "S1", ItemType.BOOK, 1, new_result.loan.loan_id
                )
                self.assertTrue(old_return)
                self.assertIn("Fine: 1", old_output.getvalue())
                self.assertEqual(new_return.fine, 1)
                self.assertEqual(
                    source.execute("SELECT available FROM books WHERE id=1").fetchone()[0],
                    target.get_item(ItemType.BOOK, 1).available_copies,
                )
                source.close()
                target.close()
            FrozenDateTime.value = datetime(2026, 11, 1, 10, 0)


if __name__ == "__main__":
    unittest.main()
