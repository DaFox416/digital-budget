from collections.abc import Iterable
from decimal import Decimal

from app.domain.money import to_money


def account_balance(initial_balance: Decimal, movement_amounts: Iterable[Decimal]) -> Decimal:
    """Balance = initial balance + sum of the signed real amounts of active movements.

    Callers pass only non-deleted movements (or their pre-aggregated total).
    For a credit account a negative balance is debt.
    """
    return to_money(initial_balance + sum(movement_amounts, Decimal("0")))


def credit_debt(balance: Decimal) -> Decimal:
    """What you owe on a credit account. Negative means the card has a credit in your favor."""
    return to_money(-balance)
