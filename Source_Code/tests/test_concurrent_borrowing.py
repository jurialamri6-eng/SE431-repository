"""Concurrent borrowing preserves stock and per-member limits on both engines."""

from __future__ import annotations

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from threading import Barrier

from library_system.factory import open_storage
from library_system.models import BorrowableItem, ItemType, LoanPolicy, Member
from library_system.service import LendingService


class ConcurrentBorrowingTests(unittest.TestCase):
    engines = ("sqlite", "duckdb")

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)

    def _database(self, name: str) -> str:
        return str(Path(self.tempdir.name) / f"{name}.db")

    @staticmethod
    def _policies() -> dict[ItemType, LoanPolicy]:
        return {ItemType.BOOK: LoanPolicy(maximum_open_loans=3)}

    def _prepare(self, engine: str, path: str, item_count: int) -> None:
        storage = open_storage(engine, path)
        try:
            storage.create_schema()
            with storage.transaction():
                storage.add_member(Member("S1", "Ali", "ACTIVE"))
                storage.add_member(Member("S2", "Sara", "ACTIVE"))
                for item_id in range(1, item_count + 1):
                    storage.add_item(
                        BorrowableItem(
                            item_id, ItemType.BOOK, f"Book {item_id}", "Author", 1, 1
                        )
                    )
        finally:
            storage.close()

    def _concurrent_attempts(
        self, engine: str, path: str, attempts: tuple[tuple[str, int], ...]
    ):
        barrier = Barrier(len(attempts))

        def borrow(member_id: str, item_id: int):
            storage = open_storage(engine, path)
            service = LendingService(storage, self._policies(), lambda: datetime(2026, 1, 1))
            try:
                barrier.wait(timeout=5)
                return service.borrow(member_id, ItemType.BOOK, item_id)
            finally:
                storage.close()

        with ThreadPoolExecutor(max_workers=len(attempts)) as executor:
            futures = [executor.submit(borrow, member, item) for member, item in attempts]
            return [future.result(timeout=10) for future in futures]

    def test_two_requests_cannot_borrow_the_last_copy(self) -> None:
        for engine in self.engines:
            with self.subTest(engine=engine):
                path = self._database(f"{engine}-last-copy")
                self._prepare(engine, path, item_count=1)
                results = self._concurrent_attempts(engine, path, (("S1", 1), ("S2", 1)))
                self.assertEqual(sum(result.success for result in results), 1)

                storage = open_storage(engine, path)
                try:
                    item = storage.get_item(ItemType.BOOK, 1)
                    self.assertEqual(item.available_copies, 0)
                    self.assertEqual(storage.count_open_loans_for_item(ItemType.BOOK, 1), 1)
                finally:
                    storage.close()

    def test_two_requests_cannot_exceed_member_limit(self) -> None:
        for engine in self.engines:
            with self.subTest(engine=engine):
                path = self._database(f"{engine}-member-limit")
                self._prepare(engine, path, item_count=4)
                storage = open_storage(engine, path)
                try:
                    service = LendingService(storage, self._policies(), lambda: datetime(2026, 1, 1))
                    self.assertTrue(service.borrow("S1", ItemType.BOOK, 1).success)
                    self.assertTrue(service.borrow("S1", ItemType.BOOK, 2).success)
                finally:
                    storage.close()

                results = self._concurrent_attempts(engine, path, (("S1", 3), ("S1", 4)))
                self.assertEqual(sum(result.success for result in results), 1)

                storage = open_storage(engine, path)
                try:
                    self.assertEqual(storage.count_open_loans("S1", ItemType.BOOK), 3)
                finally:
                    storage.close()


if __name__ == "__main__":
    unittest.main()
