"""Small named domain records shared by the application and storage adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ItemType(str, Enum):
    BOOK = "BOOK"
    EQUIPMENT = "EQUIPMENT"


@dataclass(frozen=True)
class Member:
    member_id: str
    name: str
    status: str


@dataclass(frozen=True)
class BorrowableItem:
    item_id: int
    item_type: ItemType
    name: str
    creator: str
    total_copies: int
    available_copies: int


@dataclass(frozen=True)
class Loan:
    loan_id: int
    member_id: str
    item_type: ItemType
    item_id: int
    borrowed_at: datetime
    due_at: datetime
    returned: bool


@dataclass(frozen=True)
class LoanPolicy:
    maximum_open_loans: int = 3
    loan_days: int = 14
    fine_per_overdue_day: int = 1


@dataclass(frozen=True)
class BorrowOutcome:
    success: bool
    message: str
    loan: Loan | None = None


@dataclass(frozen=True)
class ReturnOutcome:
    success: bool
    message: str
    fine: int = 0
    loan: Loan | None = None
