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
            f"{item.item_id} {item.name} - {item.creator} "
            f"Available: {item.available_copies}/{item.total_copies}"
        )


def _handle_search(service: LendingService, item_type: ItemType) -> None:
    _show_items(service.search(input("Search: "), item_type))


def _handle_borrow(service: LendingService, item_type: ItemType) -> None:
    member_id = input("Member ID: ").strip()
    label = item_type.value.title()
    try:
        item_id = int(input(f"{label} ID: "))
    except ValueError:
        print(f"Invalid {label.lower()} ID")
        return
    outcome = service.borrow(member_id, item_type, item_id)
    if outcome.success and outcome.loan:
        print(f"{outcome.message} (loan #{outcome.loan.loan_id})")
    else:
        print(outcome.message)


def _handle_return(service: LendingService, item_type: ItemType) -> None:
    member_id = input("Member ID: ").strip()
    label = item_type.value.title()
    try:
        item_id = int(input(f"{label} ID: "))
    except ValueError:
        print(f"Invalid {label.lower()} ID")
        return
    active = service.list_open_loans(member_id, item_type, item_id)
    if not active:
        print("Active loan not found")
        return
    for loan in active:
        print(f"Loan #{loan.loan_id} due {loan.due_at.isoformat()}")
    try:
        selected = int(input("Loan ID to return: "))
    except ValueError:
        print("Invalid loan ID")
        return
    outcome = service.return_item(member_id, item_type, item_id, selected)
    print(outcome.message)
    if outcome.success and outcome.fine:
        print("Fine:", outcome.fine)


def run(engine: str, database: str, item_type: ItemType = ItemType.BOOK) -> None:
    storage = open_storage(engine, database)
    equipment_mode = item_type is ItemType.EQUIPMENT
    search_label = "equipment" if equipment_mode else "books"
    loan_label = "equipment" if equipment_mode else "a book"
    try:
        storage.create_schema()
        seed_demo(storage)
        service = LendingService(storage, load_policies())
        handlers = {"1": _handle_search, "2": _handle_borrow, "3": _handle_return}
        while True:
            print("\nLIBRARY")
            print(f"1 Search {search_label}")
            print(f"2 Borrow {loan_label}")
            print(f"3 Return {loan_label}")
            print("4 Exit")
            choice = input("Choice: ").strip()
            if choice == "4":
                break
            action = handlers.get(choice)
            if action is None:
                print("Invalid choice")
                continue
            action(service, item_type)
    finally:
        storage.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="SE431 reengineered lending system")
    parser.add_argument("--engine", choices=("sqlite", "duckdb"), default="sqlite")
    parser.add_argument("--database", default="library.sqlite3")
    parser.add_argument("--item-type", choices=("book", "equipment"), default="book")
    args = parser.parse_args()
    Path(args.database).parent.mkdir(parents=True, exist_ok=True)
    run(args.engine, args.database, ItemType[args.item_type.upper()])
