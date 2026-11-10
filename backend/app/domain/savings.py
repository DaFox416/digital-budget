"""Savings mode: the seven figures, set-aside payments, leftover releases and rounding.

Invariant (docs/PLANEACION.md):
    real balance = available + set aside + card debt + savings goals + leftover - MSI pending

Every figure is derived from totals, never stored, so editing, deleting or restoring a movement
can't leave them out of sync.
"""

from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal

from app.domain.enums import AccountType
from app.domain.errors import InvalidAmountError, InvalidPreferencesError
from app.domain.money import to_money
from app.domain.summary import REAL_BALANCE_ACCOUNT_TYPES, summary_totals

DEFAULT_ROUNDING_MULTIPLE = 10
MAX_ROUNDING_MULTIPLE = 1000

# Accounts whose movements move "available"; savings accounts (Sobrante, goals) don't
AVAILABLE_ACCOUNT_TYPES = REAL_BALANCE_ACCOUNT_TYPES | {AccountType.CREDIT}


@dataclass(frozen=True)
class AccountTotals:
    type: AccountType
    # Initial balance + real amounts of its non-deleted movements
    balance: Decimal
    # Initial balance + accounting amounts of its non-deleted movements
    accounting_balance: Decimal


@dataclass(frozen=True)
class SavingsInputs:
    accounts: list[AccountTotals]
    # Installments of non-deleted MSI purchases already charged to "available": their
    # accounting amounts (what "available" lost)
    installments_charged_accounting: Decimal
    # Installments not charged yet, by their billed amount (they're inside the card debt)
    installments_pending: Decimal
    # Amounts of commitments without a non-deleted payment
    commitments_pending: Decimal
    # Leftover the user moved back to "available"
    leftover_released: Decimal
    # Savings goals arrive in v1
    savings_goals: Decimal = Decimal("0.00")


@dataclass(frozen=True)
class SavingsFigures:
    real_balance: Decimal
    available: Decimal
    set_aside: Decimal
    card_debt: Decimal
    savings_goals: Decimal
    leftover: Decimal
    installments_pending: Decimal

    def invariant_holds(self) -> bool:
        return self.real_balance == (
            self.available
            + self.set_aside
            + self.card_debt
            + self.savings_goals
            + self.leftover
            - self.installments_pending
        )


def savings_figures(inputs: SavingsInputs) -> SavingsFigures:
    accounts = [item for item in inputs.accounts if item.type in AVAILABLE_ACCOUNT_TYPES]
    totals = summary_totals((item.type, item.balance) for item in accounts)
    accounting = sum((item.accounting_balance for item in accounts), Decimal("0"))
    # real - accounting of each movement; an MSI purchase adds -total here (its accounting is 0)
    differences = sum((item.balance - item.accounting_balance for item in accounts), Decimal("0"))

    available = (
        accounting
        - inputs.installments_charged_accounting
        - inputs.commitments_pending
        - inputs.savings_goals
        + inputs.leftover_released
    )
    # The MSI terms give back the -total of each purchase, leaving only the rounding of the
    # installments already charged (accounting - amount)
    leftover = (
        differences
        + inputs.installments_charged_accounting
        + inputs.installments_pending
        - inputs.leftover_released
    )
    return SavingsFigures(
        real_balance=totals.real_balance,
        available=to_money(available),
        set_aside=to_money(inputs.commitments_pending),
        card_debt=totals.card_debt,
        savings_goals=to_money(inputs.savings_goals),
        leftover=to_money(leftover),
        installments_pending=to_money(inputs.installments_pending),
    )


def validate_rounding_multiple(multiple: int) -> int:
    if not 1 <= multiple <= MAX_ROUNDING_MULTIPLE:
        raise InvalidPreferencesError(
            f"Rounding multiple must be between 1 and {MAX_ROUNDING_MULTIPLE}"
        )
    return multiple


def releasable_leftover(leftover: Decimal, multiple: int) -> Decimal:
    """The most leftover that can go back to "available": whole multiples of the rounding."""
    if leftover <= 0:
        return Decimal("0.00")
    step = Decimal(multiple)
    return to_money((leftover / step).to_integral_value(ROUND_FLOOR) * step)


def validate_leftover_release(
    amount: Decimal | int | str, leftover: Decimal, multiple: int
) -> Decimal:
    value = to_money(amount)
    if value <= 0:
        raise InvalidAmountError("Amount must be greater than zero")
    if value % Decimal(multiple) != 0:
        raise InvalidAmountError(f"Amount must be a multiple of {multiple}")
    if value > leftover:
        raise InvalidAmountError(f"Amount is more than the leftover ({leftover})")
    return value


def commitment_payment_accounting(real: Decimal, commitment_amount: Decimal) -> Decimal:
    """Default accounting amount (positive) of an expense that pays a commitment.

    It consumes the commitment, not "available": paying 487 for a 500 commitment puts 13 into
    the leftover. If it cost more, accounting can't go below real (savings mode rule 1), so the
    extra comes out of "available".
    """
    return to_money(max(real, commitment_amount))
