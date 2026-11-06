"""Rules for creating movements.

Amounts are stored with a sign: money leaving an account is negative and money
entering it is positive. Callers pass positive magnitudes; these functions apply
the sign that matches the movement type.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal

from app.domain.enums import AccountType, MovementType
from app.domain.errors import InvalidAmountError, InvalidMovementError
from app.domain.money import to_money

# Savings accounts don't take expenses or income directly (they're filled from "available").
EXPENSE_INCOME_ACCOUNT_TYPES = frozenset({AccountType.DEBIT, AccountType.CASH, AccountType.CREDIT})
TRANSFER_SOURCE_ACCOUNT_TYPES = frozenset({AccountType.DEBIT, AccountType.CASH})


@dataclass(frozen=True)
class SignedAmounts:
    real_amount: Decimal
    accounting_amount: Decimal


@dataclass(frozen=True)
class AccountRef:
    id: uuid.UUID
    type: AccountType


@dataclass(frozen=True)
class TransferPlan:
    movement_type: MovementType
    source_amount: Decimal
    destination_amount: Decimal


def signed_amounts(
    movement_type: MovementType,
    account_type: AccountType,
    amount: Decimal | int | str,
    accounting_amount: Decimal | int | str | None = None,
) -> SignedAmounts:
    """Signed real and accounting amounts for an expense or an income.

    The accounting amount defaults to the real amount (simple mode).
    """
    if movement_type not in (MovementType.EXPENSE, MovementType.INCOME):
        raise InvalidMovementError("Use plan_transfer for transfers and card payments")
    if account_type not in EXPENSE_INCOME_ACCOUNT_TYPES:
        raise InvalidMovementError(f"A {account_type} account can't have expenses or income")

    real = to_money(amount)
    accounting = real if accounting_amount is None else to_money(accounting_amount)

    if real <= 0:
        raise InvalidAmountError("Amount must be greater than zero")
    if accounting < 0:
        raise InvalidAmountError("Accounting amount can't be negative")

    sign = -1 if movement_type is MovementType.EXPENSE else 1
    return SignedAmounts(real_amount=real * sign, accounting_amount=accounting * sign)


def plan_transfer(
    source: AccountRef, destination: AccountRef, amount: Decimal | int | str
) -> TransferPlan:
    """Plan the two legs of a transfer.

    Debit/cash to debit/cash is a transfer; debit/cash to a credit card is a card payment.
    """
    if source.id == destination.id:
        raise InvalidMovementError("Source and destination must be different accounts")
    if source.type not in TRANSFER_SOURCE_ACCOUNT_TYPES:
        raise InvalidMovementError(f"Can't transfer from a {source.type} account")

    if destination.type in TRANSFER_SOURCE_ACCOUNT_TYPES:
        movement_type = MovementType.TRANSFER
    elif destination.type is AccountType.CREDIT:
        movement_type = MovementType.CARD_PAYMENT
    else:
        raise InvalidMovementError(f"Can't transfer to a {destination.type} account")

    value = to_money(amount)
    if value <= 0:
        raise InvalidAmountError("Amount must be greater than zero")

    return TransferPlan(movement_type=movement_type, source_amount=-value, destination_amount=value)
