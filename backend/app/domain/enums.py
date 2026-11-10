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


class SavingsMode(StrEnum):
    """Simple: accounting always equals real. Savings: they can differ (see docs/PLANEACION.md)."""

    SIMPLE = "simple"
    SAVINGS = "savings"


class WarningLevel(StrEnum):
    """Warnings before saving a credit card purchase in savings mode. They never block."""

    OVER_AVAILABLE = "over_available"  # Level 1: accounting amount above "available"
    OVER_REAL_BALANCE = "over_real_balance"  # Level 2: real amount above the real balance
