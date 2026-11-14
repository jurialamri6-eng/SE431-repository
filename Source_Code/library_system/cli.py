"""Small console adapter; input/output stays outside circulation rules."""

from __future__ import annotations

import argparse
from pathlib import Path
import tomllib

from .factory import open_storage
from .models import BorrowableItem, ItemType, LoanPolicy, Member
from .service import LendingService


DEFAULT_POLICY_FILE = Path(__file__).parents[1] / "config" / "lending_policy.toml"


def load_policies(path: Path = DEFAULT_POLICY_FILE) -> dict[ItemType, LoanPolicy]:
    with path.open("rb") as file:
        values = tomllib.load(file)
    return {
        ItemType[item_type]: LoanPolicy(
            maximum_open_loans=policy["maximum_open_loans"],
            loan_days=policy["loan_days"],
            fine_per_overdue_day=policy["fine_per_overdue_day"],
        )
        for item_type, policy in values.items()
    }


def seed_demo(storage) -> None:
    if not storage.is_empty():
        return
    with storage.transaction():
        storage.add_member(Member("S1", "Ali", "ACTIVE"))
        storage.add_member(Member("S2", "Sara", "ACTIVE"))
        storage.add_item(BorrowableItem(1, ItemType.BOOK, "Clean Code", "Robert Martin", 2, 2))
        storage.add_item(BorrowableItem(2, ItemType.BOOK, "Refactoring", "Martin Fowler", 2, 2))
        storage.add_item(BorrowableItem(3, ItemType.BOOK, "Design Patterns", "Gamma et al.", 1, 1))
        storage.add_item(BorrowableItem(1, ItemType.EQUIPMENT, "Laptop", "Demo inventory", 2, 2))
        storage.add_item(BorrowableItem(2, ItemType.EQUIPMENT, "Projector", "Demo inventory", 1, 1))
        storage.add_item(BorrowableItem(3, ItemType.EQUIPMENT, "Camera", "Demo inventory", 1, 1))
        storage.add_item(
            BorrowableItem(4, ItemType.EQUIPMENT, "Lab instrument", "Demo inventory", 1, 1)
        )


def _show_items(items: list[BorrowableItem]) -> None:
    for item in items:
        print(
            f"{item.item_type.value} {item.item_id}: {item.name} — {item.creator} "
            f"Available: {item.available_copies}/{item.total_copies}"
        )


def _read_item_type() -> ItemType:
    raw = input("Item type (book/equipment): ").strip().upper()
    if raw.startswith("E"):
        return ItemType.EQUIPMENT
    if raw.startswith("B"):
        return ItemType.BOOK
    raise ValueError("Choose 'book' or 'equipment'.")


def run(engine: str, database: str) -> None:
    storage = open_storage(engine, database)
    storage.create_schema()
    seed_demo(storage)
    service = LendingService(storage, load_policies())
    try:
        while True:
            print("\nLIBRARY")
            print("1 Search")
            print("2 Borrow")
            print("3 Return")
            print("4 Exit")
            choice = input("Choice: ").strip()
            if choice == "1":
                _show_items(service.search(input("Search: ")))
            elif choice == "2":
                member_id = input("Member ID: ").strip()
                try:
                    item_type = _read_item_type()
                    item_id = int(input("Item ID: "))
                except ValueError:
                    print("Invalid item type or ID")
                    continue
                outcome = service.borrow(member_id, item_type, item_id)
                print(outcome.message)
                if outcome.success and outcome.loan:
                    print(f"Loan ID: {outcome.loan.loan_id}")
            elif choice == "3":
                member_id = input("Member ID: ").strip()
                try:
                    item_type = _read_item_type()
                    item_id = int(input("Item ID: "))
                except ValueError:
                    print("Invalid item type or ID")
                    continue
                active = service.list_open_loans(member_id, item_type, item_id)
                if not active:
                    print("Active loan not found")
                    continue
                for loan in active:
                    print(f"Loan #{loan.loan_id} due {loan.due_at.isoformat()}")
                selected = int(input("Loan ID to return: "))
                outcome = service.return_item(member_id, item_type, item_id, selected)
                print(outcome.message)
                if outcome.success and outcome.fine:
                    print("Fine:", outcome.fine)
            elif choice == "4":
                break
            else:
                print("Invalid choice")
    finally:
        storage.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="SE431 reengineered lending system")
    parser.add_argument("--engine", choices=("sqlite", "duckdb"), default="sqlite")
    parser.add_argument("--database", default="library.sqlite3")
    args = parser.parse_args()
    Path(args.database).parent.mkdir(parents=True, exist_ok=True)
    run(args.engine, args.database)
