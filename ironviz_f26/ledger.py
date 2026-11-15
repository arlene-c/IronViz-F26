from __future__ import annotations

from collections import defaultdict
from typing import Optional


class Ledger:
    """Minimal budget/tenant ledger for Phase 1 validation."""

    def __init__(self, budget: int):
        self.budget = int(budget)
        if self.budget < 0:
            raise ValueError("budget must be non-negative")
        self.global_remaining = self.budget
        self.global_spent = 0
        self._tenant_spent = defaultdict(int)
        self._tenant_reserved = defaultdict(int)
        self._reservations: dict[str, tuple[str, int]] = {}

    def reserve(self, tenant: str, amount: int, reservation_id: Optional[str] = None) -> None:
        amount = int(amount)
        if amount < 0:
            raise ValueError("reservation amount must be non-negative")
        if reservation_id is not None and reservation_id in self._reservations:
            raise ValueError(f"Duplicate reservation id: {reservation_id!r}")
        if self.global_remaining < amount:
            raise ValueError(f"Insufficient global budget for tenant {tenant!r}: {amount} > {self.global_remaining}")
        self.global_remaining -= amount
        self._tenant_reserved[tenant] += amount
        if reservation_id is not None:
            self._reservations[reservation_id] = (tenant, amount)

    def settle(self, tenant: str, released_surplus: int, reservation_id: Optional[str] = None) -> None:
        released_surplus = int(released_surplus)
        if reservation_id is None and released_surplus < 0:
            raise ValueError("settlement surplus must be non-negative")

        if reservation_id is None:
            if any(owner == tenant for owner, _ in self._reservations.values()):
                raise ValueError("named reservations require reservation_id settlement")
            before_reserved = self._tenant_reserved.get(tenant, 0)
            if released_surplus > before_reserved:
                raise ValueError("settlement surplus exceeds outstanding reservation")
            settlement_increment = max(0, before_reserved - released_surplus)
            self._tenant_spent[tenant] += settlement_increment
            self.global_spent += settlement_increment
            self.global_remaining += released_surplus
            self._tenant_reserved[tenant] = 0
            return

        try:
            reserved_tenant, reserved_amount = self._reservations.pop(reservation_id)
        except KeyError as exc:
            raise KeyError(f"Unknown reservation id: {reservation_id!r}") from exc
        if reserved_tenant != tenant:
            self._reservations[reservation_id] = (reserved_tenant, reserved_amount)
            raise ValueError(f"Reservation {reservation_id!r} belongs to {reserved_tenant!r}, not {tenant!r}")
        if released_surplus > reserved_amount:
            self._reservations[reservation_id] = (reserved_tenant, reserved_amount)
            raise ValueError("settlement surplus cannot exceed the reservation")

        actual_spend = reserved_amount - released_surplus
        self._tenant_spent[tenant] += actual_spend
        self.global_spent += actual_spend
        self.global_remaining += released_surplus
        self._tenant_reserved[tenant] -= reserved_amount

    def tenant_spent(self, tenant: str) -> int:
        return self._tenant_spent.get(tenant, 0)

    def tenant_remaining(self, tenant: str) -> int:
        return self.budget - self.tenant_spent(tenant) - self._tenant_reserved.get(tenant, 0)

    def total_reserved(self) -> int:
        return sum(self._tenant_reserved.values())
