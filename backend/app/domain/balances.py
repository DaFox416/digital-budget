from collections.abc import Iterable
from decimal import Decimal

from app.domain.errors import CreditLimitExceededError
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


def credit_available(credit_limit: Decimal, balance: Decimal) -> Decimal:
    """Credit you can still use: limit - debt.

    A credit in your favor (positive balance) adds to it. MSI purchases are already in the
    debt for their full total (one expense on the purchase date), so they need no extra step.
    """
    return to_money(credit_limit - credit_debt(balance))


def credit_limit_excess(amount: Decimal, available: Decimal) -> Decimal | None:
    """How much a card purchase goes over the card's available credit, or None if it fits.

    `amount` is a positive magnitude (an MSI purchase passes its total). Using exactly all of
    the available credit is allowed.
    """
    if amount > available:
        return to_money(amount - available)
    return None


def check_credit_limit(amount: Decimal, available: Decimal) -> None:
    """Reject a card purchase that goes over the available credit (no "save anyway")."""
    excess = credit_limit_excess(amount, available)
    if excess is not None:
        raise CreditLimitExceededError(excess)
