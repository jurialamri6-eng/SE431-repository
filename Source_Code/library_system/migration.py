"""Verified, one-way migration from the supplied SQLite schema."""

from __future__ import annotations

import argparse
import csv
import sqlite3
from datetime import datetime
from pathlib import Path

from .factory import open_storage
from .models import BorrowableItem, ItemType, Loan, Member


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
        members = source.execute(
            "SELECT id, name, status FROM members ORDER BY id"
        ).fetchall()
        columns = {row[1] for row in source.execute("PRAGMA table_info(books)")}
        if "available" not in columns:
            raise ValueError("Expected the original books.available column.")
        books = source.execute(
            "SELECT id, title, author, available FROM books ORDER BY id"
        ).fetchall()
        source_loans = source.execute(
            """SELECT id, member_id, book_id, borrow_date, due_date, returned
               FROM loans ORDER BY id"""
        ).fetchall()

        inventory: dict[int, int] = {}
        if inventory_csv is not None:
            with Path(inventory_csv).open(newline="", encoding="utf-8-sig") as file:
                for row in csv.DictReader(file):
                    book_id = int(row["book_id"])
                    count = int(row["total_copies"])
                    if book_id in inventory or count < 0:
                        raise ValueError("Inventory IDs must be unique and counts non-negative.")
                    inventory[book_id] = count
        book_ids = {row[0] for row in books}
        if set(inventory) - book_ids:
            raise ValueError("Inventory contains a book ID absent from the legacy database.")

        active_per_book: dict[int, int] = {}
        member_ids = {row[0] for row in members}
        for loan in source_loans:
            if loan[1] not in member_ids:
                raise ValueError(f"Loan {loan[0]} refers to a missing member.")
            if loan[2] not in book_ids:
                raise ValueError(f"Loan {loan[0]} refers to a missing book.")
            if not loan[5]:
                active_per_book[loan[2]] = active_per_book.get(loan[2], 0) + 1

        items: list[BorrowableItem] = []
        for book_id, title, author, old_available in books:
            active = active_per_book.get(book_id, 0)
            if old_available not in (0, 1) or active > 1:
                raise ValueError(f"Book {book_id} has invalid legacy availability or loans.")
            if bool(old_available) == bool(active):
                raise ValueError(
                    f"Book {book_id} has ambiguous legacy stock; reconcile it before migration."
                )
            total = inventory.get(book_id, 1)
            if total < active:
                raise ValueError(f"Book {book_id} has fewer copies than its open loans.")
            available = total - active
            items.append(
                BorrowableItem(
                    item_id=book_id,
                    item_type=ItemType.BOOK,
                    name=title,
                    creator=author or "",
                    total_copies=total,
                    available_copies=available,
                )
            )

        storage.create_schema()
        if not storage.is_empty() or storage.counts()["loans"]:
            raise ValueError("Migration destination must not contain application records.")
        with storage.transaction():
            for member_id, name, status in members:
                storage.add_member(Member(member_id, name or "", status))
            for item in items:
                storage.add_item(item)
            for loan_id, member_id, book_id, borrowed_at, due_at, returned in source_loans:
                storage.import_loan(
                    Loan(
                        loan_id=loan_id,
                        member_id=member_id,
                        item_type=ItemType.BOOK,
                        item_id=book_id,
                        borrowed_at=datetime.fromisoformat(borrowed_at),
                        due_at=datetime.fromisoformat(due_at),
                        returned=bool(returned),
                    )
                )

        counts = storage.counts()
        expected = {"members": len(members), "items": len(books), "loans": len(source_loans)}
        if counts != expected:
            raise RuntimeError(f"Migration row-count mismatch: expected {expected}, got {counts}.")
        for item in storage.list_items(ItemType.BOOK):
            open_count = storage.count_open_loans_for_item(item.item_type, item.item_id)
            if item.available_copies + open_count != item.total_copies:
                raise RuntimeError(f"Migrated stock validation failed for book {item.item_id}.")
        return counts
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
