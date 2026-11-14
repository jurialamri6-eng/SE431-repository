"""Maintenance prototype before the Phase 3 separation-of-concerns refactor.

This file is kept as an evolution snapshot for the SE431 comparison. It already
implements MR-01 and MR-02, but deliberately keeps SQL and policy in the same
functions so Phase 3 can separate those responsibilities in the next commit.
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


DEFAULT_ENGINE = "sqlite"
DEFAULT_DATABASE = "library.sqlite3"
MAX_OPEN_LOANS = 3
LOAN_DAYS = 14
FINE_PER_DAY = 1


def open_database(engine: str, path: str | Path) -> Any:
    """Open a SQLite or DuckDB connection, selected by the user at startup."""
    if engine == "sqlite":
        connection = sqlite3.connect(str(path), isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
    if engine == "duckdb":
        try:
            import duckdb
        except ImportError as exc:
            raise RuntimeError("Install the pinned DuckDB dependency first.") from exc
        return duckdb.connect(str(path))
    raise ValueError("Engine must be 'sqlite' or 'duckdb'.")


def initialize_schema(connection: Any, engine: str, seed: bool = True) -> None:
    """Create the shared logical schema; demo copy counts are sample data."""
    connection.execute(
        """CREATE TABLE IF NOT EXISTS members (
               id TEXT PRIMARY KEY,
               name TEXT NOT NULL,
               status TEXT NOT NULL
           )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS items (
               item_type TEXT NOT NULL CHECK (item_type IN ('BOOK', 'EQUIPMENT')),
               item_id INTEGER NOT NULL,
               name TEXT NOT NULL,
               creator TEXT NOT NULL DEFAULT '',
               total_copies INTEGER NOT NULL CHECK (total_copies >= 0),
               available_copies INTEGER NOT NULL CHECK (
                   available_copies >= 0 AND available_copies <= total_copies
               ),
               PRIMARY KEY (item_type, item_id)
           )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS loans (
               id INTEGER PRIMARY KEY,
               member_id TEXT NOT NULL REFERENCES members(id),
               item_type TEXT NOT NULL,
               item_id INTEGER NOT NULL,
               borrow_date TEXT NOT NULL,
               due_date TEXT NOT NULL,
               returned INTEGER NOT NULL DEFAULT 0 CHECK (returned IN (0, 1)),
               FOREIGN KEY (item_type, item_id) REFERENCES items(item_type, item_id)
           )"""
    )
    if not seed:
        return
    if connection.execute("SELECT COUNT(*) FROM members").fetchone()[0] == 0:
        connection.executemany(
            "INSERT INTO members(id, name, status) VALUES (?, ?, ?)",
            [("S1", "Ali", "ACTIVE"), ("S2", "Sara", "ACTIVE")],
        )
    if connection.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 0:
        connection.executemany(
            """INSERT INTO items
               (item_type, item_id, name, creator, total_copies, available_copies)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                ("BOOK", 1, "Clean Code", "Robert Martin", 2, 2),
                ("BOOK", 2, "Refactoring", "Martin Fowler", 2, 2),
                ("BOOK", 3, "Design Patterns", "Gamma et al.", 1, 1),
            ],
        )


def search_books(connection: Any, text: str) -> list[tuple[Any, ...]]:
    """Search book titles and authors; SQL wildcard characters remain active."""
    pattern = f"%{text}%"
    rows = connection.execute(
        """SELECT item_id, name, creator, available_copies, total_copies
           FROM items
           WHERE item_type = 'BOOK'
             AND (lower(name) LIKE lower(?) OR lower(creator) LIKE lower(?))
           ORDER BY item_id""",
        (pattern, pattern),
    ).fetchall()
    for item_id, name, creator, available, total in rows:
        print(f"{item_id} {name} - {creator} Available: {available}/{total}")
    return rows


def borrow(
    connection: Any,
    engine: str,
    member_id: str,
    item_id: int,
    item_type: str = "BOOK",
    now: datetime | None = None,
) -> bool:
    """Long pre-refactor operation: validation, policy, SQL, and messages."""
    connection.execute("BEGIN IMMEDIATE" if engine == "sqlite" else "BEGIN TRANSACTION")
    try:
        member = connection.execute(
            "SELECT id, status FROM members WHERE id = ?", (member_id,)
        ).fetchone()
        if not member:
            connection.rollback()
            print("Member not found")
            return False
        if member[1] != "ACTIVE":
            connection.rollback()
            print("Member is not active")
            return False

        item = connection.execute(
            """SELECT item_id, available_copies FROM items
               WHERE item_type = ? AND item_id = ?""",
            (item_type, item_id),
        ).fetchone()
        if not item:
            connection.rollback()
            print("Book not found" if item_type == "BOOK" else "Equipment not found")
            return False
        if item[1] < 1:
            connection.rollback()
            print("Book is unavailable" if item_type == "BOOK" else "Equipment is unavailable")
            return False

        active_count = connection.execute(
            "SELECT COUNT(*) FROM loans WHERE member_id = ? AND returned = 0",
            (member_id,),
        ).fetchone()[0]
        if active_count >= MAX_OPEN_LOANS:
            connection.rollback()
            print("Borrowing limit reached")
            return False

        borrowed_at = now or datetime.now()
        due_at = borrowed_at + timedelta(days=LOAN_DAYS)
        next_id = connection.execute(
            "SELECT COALESCE(MAX(id), 0) + 1 FROM loans"
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO loans
               (id, member_id, item_type, item_id, borrow_date, due_date, returned)
               VALUES (?, ?, ?, ?, ?, ?, 0)""",
            (
                next_id,
                member_id,
                item_type,
                item_id,
                borrowed_at.isoformat(),
                due_at.isoformat(),
            ),
        )
        connection.execute(
            """UPDATE items SET available_copies = available_copies - 1
               WHERE item_type = ? AND item_id = ? AND available_copies > 0""",
            (item_type, item_id),
        )
        updated = connection.execute(
            "SELECT available_copies FROM items WHERE item_type = ? AND item_id = ?",
            (item_type, item_id),
        ).fetchone()[0]
        if updated != item[1] - 1:
            raise RuntimeError("Stock changed during the borrowing transaction.")
        connection.commit()
        print(f"Book borrowed. Due: {due_at.date()} (loan #{next_id})")
        return True
    except Exception:
        connection.rollback()
        raise


def list_open_loans(
    connection: Any, member_id: str, item_id: int
) -> list[tuple[Any, ...]]:
    return connection.execute(
        """SELECT id, borrow_date, due_date FROM loans
           WHERE member_id = ? AND item_type = 'BOOK' AND item_id = ? AND returned = 0
           ORDER BY due_date, id""",
        (member_id, item_id),
    ).fetchall()


def return_book(
    connection: Any,
    engine: str,
    member_id: str,
    item_id: int,
    loan_id: int,
    now: datetime | None = None,
) -> int | None:
    """Close one chosen loan and restore exactly one copy in one transaction."""
    connection.execute("BEGIN IMMEDIATE" if engine == "sqlite" else "BEGIN TRANSACTION")
    try:
        loan = connection.execute(
            """SELECT id, due_date FROM loans
               WHERE id = ? AND member_id = ? AND item_type = 'BOOK'
                 AND item_id = ? AND returned = 0""",
            (loan_id, member_id, item_id),
        ).fetchone()
        if not loan:
            connection.rollback()
            print("Active loan not found")
            return None
        item = connection.execute(
            """SELECT available_copies, total_copies FROM items
               WHERE item_type = 'BOOK' AND item_id = ?""",
            (item_id,),
        ).fetchone()
        if not item or item[0] >= item[1]:
            raise RuntimeError("Cannot restore a copy: inventory is inconsistent.")

        today = now or datetime.now()
        due = datetime.fromisoformat(loan[1])
        late_days = (today - due).days
        fine = late_days * FINE_PER_DAY if late_days > 0 else 0
        connection.execute(
            "UPDATE loans SET returned = 1 WHERE id = ? AND returned = 0", (loan_id,)
        )
        connection.execute(
            """UPDATE items SET available_copies = available_copies + 1
               WHERE item_type = 'BOOK' AND item_id = ? AND available_copies < total_copies""",
            (item_id,),
        )
        updated = connection.execute(
            "SELECT available_copies FROM items WHERE item_type = 'BOOK' AND item_id = ?",
            (item_id,),
        ).fetchone()[0]
        if updated != item[0] + 1:
            raise RuntimeError("Stock changed during the return transaction.")
        connection.commit()
        print("Book returned")
        if fine:
            print("Fine:", fine)
        return fine
    except Exception:
        connection.rollback()
        raise


def _legacy_rows(source: sqlite3.Connection) -> tuple[list[tuple[Any, ...]], ...]:
    members = source.execute("SELECT id, name, status FROM members ORDER BY id").fetchall()
    book_columns = {row[1] for row in source.execute("PRAGMA table_info(books)")}
    if "available" not in book_columns:
        raise ValueError("The source is not the supplied single-copy books schema.")
    books = source.execute(
        "SELECT id, title, author, available FROM books ORDER BY id"
    ).fetchall()
    loans = source.execute(
        """SELECT id, member_id, book_id, borrow_date, due_date, returned
           FROM loans ORDER BY id"""
    ).fetchall()
    return members, books, loans


def migrate_legacy_sqlite(
    source_path: str | Path,
    destination_path: str | Path,
    engine: str = "duckdb",
    inventory_csv: str | Path | None = None,
) -> dict[str, int]:
    """Copy legacy rows into an empty new database; source data is left intact."""
    if Path(source_path).resolve() == Path(destination_path).resolve():
        raise ValueError("Use a separate destination so the legacy source stays unchanged.")
    source = sqlite3.connect(str(source_path))
    destination = open_database(engine, destination_path)
    try:
        members, books, loans = _legacy_rows(source)
        inventory: dict[int, int] = {}
        if inventory_csv:
            with Path(inventory_csv).open(newline="", encoding="utf-8-sig") as file:
                for row in csv.DictReader(file):
                    item_id = int(row["book_id"])
                    count = int(row["total_copies"])
                    if count < 0 or item_id in inventory:
                        raise ValueError("Inventory rows must have unique IDs and non-negative copies.")
                    inventory[item_id] = count
        known_book_ids = {row[0] for row in books}
        if set(inventory) - known_book_ids:
            raise ValueError("Inventory CSV contains a book ID absent from the legacy database.")

        initialize_schema(destination, engine, seed=False)
        for table in ("members", "items", "loans"):
            if destination.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]:
                raise ValueError("Migration destination must be empty.")

        open_counts: dict[int, int] = {}
        for row in loans:
            if not row[5]:
                open_counts[row[2]] = open_counts.get(row[2], 0) + 1
        item_rows = []
        for item_id, title, author, old_available in books:
            open_count = open_counts.get(item_id, 0)
            default_total = 1
            if old_available not in (0, 1) or old_available + open_count != default_total:
                if item_id not in inventory:
                    raise ValueError(
                        f"Book {item_id} has ambiguous legacy stock; reconcile inventory before migration."
                    )
            total = inventory.get(item_id, default_total)
            if total < open_count:
                raise ValueError(f"Book {item_id} has fewer copies than open loans.")
            if item_id in inventory and total - open_count != old_available:
                # Verified quantities supersede the old Boolean but never the loan history.
                available = total - open_count
            else:
                available = old_available
            item_rows.append(("BOOK", item_id, title, author or "", total, available))

        destination.execute("BEGIN IMMEDIATE" if engine == "sqlite" else "BEGIN TRANSACTION")
        destination.executemany(
            "INSERT INTO members(id, name, status) VALUES (?, ?, ?)", members
        )
        destination.executemany(
            """INSERT INTO items
               (item_type, item_id, name, creator, total_copies, available_copies)
               VALUES (?, ?, ?, ?, ?, ?)""",
            item_rows,
        )
        destination.executemany(
            """INSERT INTO loans
               (id, member_id, item_type, item_id, borrow_date, due_date, returned)
               VALUES (?, ?, 'BOOK', ?, ?, ?, ?)""",
            [(loan[0], loan[1], loan[2], loan[3], loan[4], loan[5]) for loan in loans],
        )
        counts = {
            "members": destination.execute("SELECT COUNT(*) FROM members").fetchone()[0],
            "items": destination.execute("SELECT COUNT(*) FROM items").fetchone()[0],
            "loans": destination.execute("SELECT COUNT(*) FROM loans").fetchone()[0],
        }
        if counts != {"members": len(members), "items": len(books), "loans": len(loans)}:
            raise RuntimeError("Migration row-count validation failed.")
        destination.commit()
        return counts
    except Exception:
        try:
            destination.rollback()
        except Exception:
            pass
        raise
    finally:
        source.close()
        destination.close()


def run(engine: str = DEFAULT_ENGINE, database: str = DEFAULT_DATABASE) -> None:
    connection = open_database(engine, database)
    initialize_schema(connection, engine)
    try:
        while True:
            print("\nLIBRARY")
            print("1 Search books")
            print("2 Borrow a book")
            print("3 Return a book")
            print("4 Exit")
            choice = input("Choice: ").strip()
            if choice == "1":
                search_books(connection, input("Search: "))
            elif choice == "2":
                member_id = input("Member ID: ").strip()
                item_id = int(input("Book ID: "))
                borrow(connection, engine, member_id, item_id)
            elif choice == "3":
                member_id = input("Member ID: ").strip()
                item_id = int(input("Book ID: "))
                loans = list_open_loans(connection, member_id, item_id)
                if not loans:
                    print("Active loan not found")
                    continue
                for loan in loans:
                    print(f"Loan #{loan[0]} due {loan[2]}")
                loan_id = int(input("Loan ID to return: "))
                return_book(connection, engine, member_id, item_id, loan_id)
            elif choice == "4":
                break
            else:
                print("Invalid choice")
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="SE431 library maintenance prototype")
    parser.add_argument("--engine", choices=("sqlite", "duckdb"), default=DEFAULT_ENGINE)
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    args = parser.parse_args()
    run(args.engine, args.database)


if __name__ == "__main__":
    main()
