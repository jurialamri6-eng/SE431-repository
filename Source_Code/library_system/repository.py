"""Portable SQL implementation shared by the SQLite and DuckDB connectors."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from .models import BorrowableItem, ItemType, Loan, Member


class SQLRepository:
    """Database details stay behind this repository; callers use named records."""

    begin_statement = "BEGIN"

    def __init__(self, connection: Any) -> None:
        self.connection = connection

    @contextmanager
    def transaction(self) -> Iterator[None]:
        self.connection.execute(self.begin_statement)
        try:
            yield
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def create_schema(self) -> None:
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS members (
                   id TEXT PRIMARY KEY,
                   name TEXT NOT NULL,
                   status TEXT NOT NULL
               )"""
        )
        self.connection.execute(
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
        self.connection.execute(
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

    def add_member(self, member: Member) -> None:
        self.connection.execute(
            "INSERT INTO members(id, name, status) VALUES (?, ?, ?)",
            (member.member_id, member.name, member.status),
        )

    def add_item(self, item: BorrowableItem) -> None:
        if not 0 <= item.available_copies <= item.total_copies:
            raise ValueError("Available copies must be between zero and total copies.")
        self.connection.execute(
            """INSERT INTO items
               (item_type, item_id, name, creator, total_copies, available_copies)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                item.item_type.value,
                item.item_id,
                item.name,
                item.creator,
                item.total_copies,
                item.available_copies,
            ),
        )

    def get_member(self, member_id: str) -> Member | None:
        row = self.connection.execute(
            "SELECT id, name, status FROM members WHERE id = ?", (member_id,)
        ).fetchone()
        return Member(*row) if row else None

    @staticmethod
    def _item(row: tuple[Any, ...] | None) -> BorrowableItem | None:
        if row is None:
            return None
        return BorrowableItem(
            item_id=row[1],
            item_type=ItemType(row[0]),
            name=row[2],
            creator=row[3],
            total_copies=row[4],
            available_copies=row[5],
        )

    @staticmethod
    def _loan(row: tuple[Any, ...] | None) -> Loan | None:
        if row is None:
            return None
        from datetime import datetime

        return Loan(
            loan_id=row[0],
            member_id=row[1],
            item_type=ItemType(row[2]),
            item_id=row[3],
            borrowed_at=datetime.fromisoformat(row[4]),
            due_at=datetime.fromisoformat(row[5]),
            returned=bool(row[6]),
        )

    def get_item(self, item_type: ItemType, item_id: int) -> BorrowableItem | None:
        row = self.connection.execute(
            """SELECT item_type, item_id, name, creator, total_copies, available_copies
               FROM items WHERE item_type = ? AND item_id = ?""",
            (item_type.value, item_id),
        ).fetchone()
        return self._item(row)

    def search_items(
        self, text: str, item_type: ItemType | None = None
    ) -> list[BorrowableItem]:
        pattern = f"%{text}%"
        sql = """SELECT item_type, item_id, name, creator, total_copies, available_copies
                 FROM items
                 WHERE (lower(name) LIKE lower(?) OR lower(creator) LIKE lower(?))"""
        values: tuple[Any, ...] = (pattern, pattern)
        if item_type is not None:
            sql += " AND item_type = ?"
            values += (item_type.value,)
        sql += " ORDER BY item_type, item_id"
        rows = self.connection.execute(sql, values).fetchall()
        return [self._item(row) for row in rows if row is not None]

    def list_items(self, item_type: ItemType | None = None) -> list[BorrowableItem]:
        sql = """SELECT item_type, item_id, name, creator, total_copies, available_copies
                 FROM items"""
        values: tuple[Any, ...] = ()
        if item_type is not None:
            sql += " WHERE item_type = ?"
            values = (item_type.value,)
        sql += " ORDER BY item_type, item_id"
        return [
            self._item(row)
            for row in self.connection.execute(sql, values).fetchall()
        ]

    def count_open_loans(
        self, member_id: str, item_type: ItemType | None = None
    ) -> int:
        sql = "SELECT COUNT(*) FROM loans WHERE member_id = ? AND returned = 0"
        values: tuple[Any, ...] = (member_id,)
        if item_type is not None:
            sql += " AND item_type = ?"
            values += (item_type.value,)
        return self.connection.execute(sql, values).fetchone()[0]

    def count_open_loans_for_item(self, item_type: ItemType, item_id: int) -> int:
        return self.connection.execute(
            """SELECT COUNT(*) FROM loans
               WHERE item_type = ? AND item_id = ? AND returned = 0""",
            (item_type.value, item_id),
        ).fetchone()[0]

    def open_loans(
        self, member_id: str, item_type: ItemType, item_id: int
    ) -> list[Loan]:
        rows = self.connection.execute(
            """SELECT id, member_id, item_type, item_id, borrow_date, due_date, returned
               FROM loans
               WHERE member_id = ? AND item_type = ? AND item_id = ? AND returned = 0
               ORDER BY due_date, id""",
            (member_id, item_type.value, item_id),
        ).fetchall()
        return [self._loan(row) for row in rows if row is not None]

    def get_open_loan(self, loan_id: int) -> Loan | None:
        row = self.connection.execute(
            """SELECT id, member_id, item_type, item_id, borrow_date, due_date, returned
               FROM loans WHERE id = ? AND returned = 0""",
            (loan_id,),
        ).fetchone()
        return self._loan(row)

    def create_loan(
        self, member_id: str, item: BorrowableItem, borrowed_at, due_at
    ) -> Loan:
        loan_id = self.connection.execute(
            "SELECT COALESCE(MAX(id), 0) + 1 FROM loans"
        ).fetchone()[0]
        self.connection.execute(
            """INSERT INTO loans
               (id, member_id, item_type, item_id, borrow_date, due_date, returned)
               VALUES (?, ?, ?, ?, ?, ?, 0)""",
            (
                loan_id,
                member_id,
                item.item_type.value,
                item.item_id,
                borrowed_at.isoformat(),
                due_at.isoformat(),
            ),
        )
        return Loan(loan_id, member_id, item.item_type, item.item_id, borrowed_at, due_at, False)

    def import_loan(self, loan: Loan) -> None:
        self.connection.execute(
            """INSERT INTO loans
               (id, member_id, item_type, item_id, borrow_date, due_date, returned)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                loan.loan_id,
                loan.member_id,
                loan.item_type.value,
                loan.item_id,
                loan.borrowed_at.isoformat(),
                loan.due_at.isoformat(),
                int(loan.returned),
            ),
        )

    def close_loan(self, loan_id: int) -> Loan | None:
        loan = self.get_open_loan(loan_id)
        if loan is None:
            return None
        self.connection.execute(
            "UPDATE loans SET returned = 1 WHERE id = ? AND returned = 0", (loan_id,)
        )
        return loan

    def decrease_available(self, item: BorrowableItem) -> None:
        if item.available_copies < 1:
            raise RuntimeError("No available copy to reserve.")
        self.connection.execute(
            """UPDATE items SET available_copies = available_copies - 1
               WHERE item_type = ? AND item_id = ? AND available_copies > 0""",
            (item.item_type.value, item.item_id),
        )
        saved = self.get_item(item.item_type, item.item_id)
        if saved is None or saved.available_copies != item.available_copies - 1:
            raise RuntimeError("Stock changed during the borrowing transaction.")

    def increase_available(self, item: BorrowableItem) -> None:
        if item.available_copies >= item.total_copies:
            raise RuntimeError("Cannot restore a copy: inventory is inconsistent.")
        self.connection.execute(
            """UPDATE items SET available_copies = available_copies + 1
               WHERE item_type = ? AND item_id = ? AND available_copies < total_copies""",
            (item.item_type.value, item.item_id),
        )
        saved = self.get_item(item.item_type, item.item_id)
        if saved is None or saved.available_copies != item.available_copies + 1:
            raise RuntimeError("Stock changed during the return transaction.")

    def counts(self) -> dict[str, int]:
        return {
            name: self.connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
            for name in ("members", "items", "loans")
        }

    def is_empty(self) -> bool:
        return self.counts()["members"] == 0 and self.counts()["items"] == 0

    def close(self) -> None:
        self.connection.close()
