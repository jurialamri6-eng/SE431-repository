"""Verified, one-way migration from the supplied SQLite schema."""

from __future__ import annotations

import argparse
import csv
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .factory import open_storage
from .models import BorrowableItem, ItemType, Loan, Member


def _fetch_all(connection: sqlite3.Connection, sql: str) -> list[dict[str, Any]]:
    cursor = connection.execute(sql)
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def _read_legacy(source: sqlite3.Connection) -> tuple[list[dict], list[dict], list[dict]]:
    members = _fetch_all(source, "SELECT id, name, status FROM members ORDER BY id")
    columns = {row["name"] for row in _fetch_all(source, "PRAGMA table_info(books)")}
    if "available" not in columns:
        raise ValueError("Expected the original books.available column.")
    books = _fetch_all(
        source, "SELECT id, title, author, available FROM books ORDER BY id"
    )
    loans = _fetch_all(
        source,
        """SELECT id, member_id, book_id, borrow_date, due_date, returned
           FROM loans ORDER BY id""",
    )
    return members, books, loans


def _read_inventory(path: str | Path | None) -> dict[int, int]:
    if path is None:
        return {}
    inventory: dict[int, int] = {}
    with Path(path).open(newline="", encoding="utf-8-sig") as file:
        for row in csv.DictReader(file):
            book_id = int(row["book_id"])
            count = int(row["total_copies"])
            if book_id in inventory or count < 0:
                raise ValueError("Inventory IDs must be unique and counts non-negative.")
            inventory[book_id] = count
    return inventory


def _active_loans_by_book(
    members: list[dict], books: list[dict], loans: list[dict]
) -> dict[int, int]:
    member_ids = {member["id"] for member in members}
    book_ids = {book["id"] for book in books}
    active: dict[int, int] = {}
    for loan in loans:
        if loan["member_id"] not in member_ids:
            raise ValueError(f"Loan {loan['id']} refers to a missing member.")
        if loan["book_id"] not in book_ids:
            raise ValueError(f"Loan {loan['id']} refers to a missing book.")
        if not loan["returned"]:
            book_id = loan["book_id"]
            active[book_id] = active.get(book_id, 0) + 1
    return active


def _build_items(
    books: list[dict], inventory: dict[int, int], active_by_book: dict[int, int]
) -> list[BorrowableItem]:
    book_ids = {book["id"] for book in books}
    if set(inventory) - book_ids:
        raise ValueError("Inventory contains a book ID absent from the legacy database.")
    items = []
    for book in books:
        book_id = book["id"]
        active = active_by_book.get(book_id, 0)
        available_flag = book["available"]
        if available_flag not in (0, 1) or active > 1:
            raise ValueError(f"Book {book_id} has invalid legacy availability or loans.")
        if bool(available_flag) == bool(active):
            raise ValueError(
                f"Book {book_id} has ambiguous legacy stock; reconcile it before migration."
            )
        total = inventory.get(book_id, 1)
        if total < active:
            raise ValueError(f"Book {book_id} has fewer copies than its open loans.")
        items.append(
            BorrowableItem(
                item_id=book_id,
                item_type=ItemType.BOOK,
                name=book["title"],
                creator=book["author"] or "",
                total_copies=total,
                available_copies=total - active,
            )
        )
    return items


def _import_records(
    storage, members: list[dict], items: list[BorrowableItem], loans: list[dict]
) -> None:
    with storage.transaction():
        for member in members:
            storage.add_member(
                Member(member["id"], member["name"] or "", member["status"])
            )
        for item in items:
            storage.add_item(item)
        for row in loans:
            storage.import_loan(
                Loan(
                    loan_id=row["id"],
                    member_id=row["member_id"],
                    item_type=ItemType.BOOK,
                    item_id=row["book_id"],
                    borrowed_at=datetime.fromisoformat(row["borrow_date"]),
                    due_at=datetime.fromisoformat(row["due_date"]),
                    returned=bool(row["returned"]),
                )
            )


def _validate_destination(storage, members: list[dict], books: list[dict], loans: list[dict]) -> dict[str, int]:
    counts = storage.counts()
    expected = {"members": len(members), "items": len(books), "loans": len(loans)}
    if counts != expected:
        raise RuntimeError(f"Migration row-count mismatch: expected {expected}, got {counts}.")
    for item in storage.list_items(ItemType.BOOK):
        open_count = storage.count_open_loans_for_item(item.item_type, item.item_id)
        if item.available_copies + open_count != item.total_copies:
            raise RuntimeError(f"Migrated stock validation failed for book {item.item_id}.")
    return counts


def migrate_legacy_sqlite(
    source_path: str | Path,
    destination_path: str | Path,
    target_engine: str = "duckdb",
    inventory_csv: str | Path | None = None,
) -> dict[str, int]:
    """Copy legacy data into an empty target and validate it; keep source intact.

    Optional inventory CSV columns: ``book_id,total_copies``. Without verified
    quantities, only consistent one-copy records can be migrated.
    """
    source_path = Path(source_path).resolve()
    destination_path = Path(destination_path).resolve()
    if source_path == destination_path:
        raise ValueError("Choose a separate destination to preserve the source database.")
    if not source_path.is_file():
        raise FileNotFoundError(source_path)

    source = sqlite3.connect(str(source_path))
    storage = open_storage(target_engine, str(destination_path))
    try:
        members, books, loans = _read_legacy(source)
        inventory = _read_inventory(inventory_csv)
        active_by_book = _active_loans_by_book(members, books, loans)
        items = _build_items(books, inventory, active_by_book)

        storage.create_schema()
        if not storage.is_empty() or storage.counts()["loans"]:
            raise ValueError("Migration destination must not contain application records.")
        _import_records(storage, members, items, loans)
        return _validate_destination(storage, members, books, loans)
    finally:
        source.close()
        storage.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate the original LMS SQLite database")
    parser.add_argument("source", help="Path to the original library.db")
    parser.add_argument("destination", help="New database path")
    parser.add_argument("--engine", choices=("sqlite", "duckdb"), default="duckdb")
    parser.add_argument("--inventory-csv", help="Verified counts: book_id,total_copies")
    args = parser.parse_args()
    result = migrate_legacy_sqlite(args.source, args.destination, args.engine, args.inventory_csv)
    print("Migration complete:", result)


if __name__ == "__main__":
    main()
