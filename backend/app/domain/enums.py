from enum import StrEnum


class AccountType(StrEnum):
    DEBIT = "debit"
    CASH = "cash"
    CREDIT = "credit"
    SAVINGS = "savings"


class MovementType(StrEnum):
    EXPENSE = "expense"
    INCOME = "income"
    TRANSFER = "transfer"
    CARD_PAYMENT = "card_payment"


TRANSFER_MOVEMENT_TYPES = frozenset({MovementType.TRANSFER, MovementType.CARD_PAYMENT})


class PaymentDueRule(StrEnum):
    """How a bank sets a card's payment due date."""

    FIXED_DAY = "fixed_day"  # e.g. always on the 5th
    DAYS_AFTER_CUTOFF = "days_after_cutoff"  # e.g. 20 days after the cutoff
