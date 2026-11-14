from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta

from library_system.cli import load_policies, seed_demo
from library_system.factory import open_storage
from library_system.models import BorrowableItem, ItemType, LoanPolicy, Member
from library_system.service import LendingService


class EquipmentReuseTests(unittest.TestCase):
    def test_shared_service_uses_item_specific_policy_in_both_engines(self) -> None:
        for engine in ("sqlite", "duckdb"):
            with self.subTest(engine=engine), tempfile.TemporaryDirectory() as directory:
                storage = open_storage(engine, f"{directory}/equipment.db")
                storage.create_schema()
                with storage.transaction():
                    storage.add_member(Member("S1", "Ali", "ACTIVE"))
                    storage.add_item(
                        BorrowableItem(1, ItemType.BOOK, "Clean Code", "R. Martin", 2, 2)
                    )
                    storage.add_item(
                        BorrowableItem(1, ItemType.EQUIPMENT, "Laptop", "Demo", 2, 2)
                    )
                now = datetime(2026, 11, 1, 10, 0)
                policies = {
                    ItemType.BOOK: LoanPolicy(3, 14, 1),
                    ItemType.EQUIPMENT: LoanPolicy(1, 7, 0),
                }
                service = LendingService(storage, policies, clock=lambda: now)
                try:
                    book = service.borrow("S1", ItemType.BOOK, 1)
                    equipment = service.borrow("S1", ItemType.EQUIPMENT, 1)
                    rejected_equipment = service.borrow("S1", ItemType.EQUIPMENT, 1)
                    self.assertTrue(book.success and equipment.success)
                    self.assertEqual(book.loan.due_at, now + timedelta(days=14))
                    self.assertEqual(equipment.loan.due_at, now + timedelta(days=7))
                    self.assertFalse(rejected_equipment.success)
                    self.assertEqual(
                        [item.item_type for item in service.search("", None)],
                        [ItemType.BOOK, ItemType.EQUIPMENT],
                    )
                finally:
                    storage.close()

    def test_sample_policies_and_inventory_are_labeled_demo_values(self) -> None:
        policies = load_policies()
        self.assertEqual(policies[ItemType.BOOK], LoanPolicy(3, 14, 1))
        self.assertEqual(policies[ItemType.EQUIPMENT], LoanPolicy(1, 7, 0))
        with tempfile.TemporaryDirectory() as directory:
            storage = open_storage("sqlite", f"{directory}/demo.db")
            storage.create_schema()
            seed_demo(storage)
            self.assertEqual(len(storage.list_items(ItemType.EQUIPMENT)), 4)
            storage.close()


if __name__ == "__main__":
    unittest.main()
