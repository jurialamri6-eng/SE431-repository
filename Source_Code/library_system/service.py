"""Lending rules without SQL, cursor handling, or console output."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable, Mapping

from .models import (
    BorrowOutcome,
    BorrowableItem,
    ItemType,
    LoanPolicy,
    Member,
    ReturnOutcome,
)
from .storage import Storage


class LendingService:
    def __init__(
        self,
        storage: Storage,
        policies: Mapping[ItemType, LoanPolicy],
        clock: Callable[[], datetime] = datetime.now,
    ) -> None:
        self.storage = storage
        self.policies = dict(policies)
        self.clock = clock

    @staticmethod
    def _member_failure(member: Member | None) -> str | None:
        if member is None:
            return "Member not found"
        if member.status != "ACTIVE":
            return "Member is not active"
        return None

    @staticmethod
    def _item_failure(item: BorrowableItem | None, item_type: ItemType) -> str | None:
        if item is None:
            return f"{item_type.value.title()} not found"
        if item.available_copies < 1:
            return f"{item_type.value.title()} is unavailable"
        return None

    @staticmethod
    def _fine_for_return(now: datetime, due_at: datetime, policy: LoanPolicy) -> int:
        completed_late_days = max(0, (now - due_at).days)
        return completed_late_days * policy.fine_per_overdue_day

    def borrow(self, member_id: str, item_type: ItemType, item_id: int) -> BorrowOutcome:
        policy = self.policies.get(item_type)
        if policy is None:
            return BorrowOutcome(False, "No lending policy is configured for this item type")

        with self.storage.transaction():
            member = self.storage.get_member(member_id)
            member_failure = self._member_failure(member)
            if member_failure:
                return BorrowOutcome(False, member_failure)

            item = self.storage.get_item(item_type, item_id)
            item_failure = self._item_failure(item, item_type)
            if item_failure:
                return BorrowOutcome(False, item_failure)

            if self.storage.count_open_loans(member_id, item_type) >= policy.maximum_open_loans:
                return BorrowOutcome(False, "Borrowing limit reached")

            borrowed_at = self.clock()
            due_at = borrowed_at + timedelta(days=policy.loan_days)
            loan = self.storage.create_loan(member_id, item, borrowed_at, due_at)
            self.storage.decrease_available(item)
            return BorrowOutcome(True, f"{item_type.value.title()} borrowed. Due: {due_at.date()}", loan)

    def return_item(
        self,
        member_id: str,
        item_type: ItemType,
        item_id: int,
        loan_id: int | None = None,
    ) -> ReturnOutcome:
        policy = self.policies.get(item_type)
        if policy is None:
            return ReturnOutcome(False, "No lending policy is configured for this item type")

        with self.storage.transaction():
            active = self.storage.open_loans(member_id, item_type, item_id)
            if not active:
                return ReturnOutcome(False, "Active loan not found")
            if loan_id is None:
                if len(active) != 1:
                    return ReturnOutcome(False, "Choose a loan ID when several copies are borrowed")
                selected = active[0]
            else:
                selected = next((loan for loan in active if loan.loan_id == loan_id), None)
                if selected is None:
                    return ReturnOutcome(False, "Active loan not found")

            item = self.storage.get_item(item_type, item_id)
            if item is None:
                raise RuntimeError("The item for this open loan is missing.")
            now = self.clock()
            closed = self.storage.close_loan(selected.loan_id)
            if closed is None:
                return ReturnOutcome(False, "Active loan not found")
            fine = self._fine_for_return(now, selected.due_at, policy)
            self.storage.increase_available(item)
            return ReturnOutcome(True, f"{item_type.value.title()} returned", fine, closed)

    def search(self, text: str, item_type: ItemType | None = None):
        return self.storage.search_items(text, item_type)

    def list_open_loans(self, member_id: str, item_type: ItemType, item_id: int):
        return self.storage.open_loans(member_id, item_type, item_id)
