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
