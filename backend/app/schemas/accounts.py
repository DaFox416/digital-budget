import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.domain.enums import AccountType, PaymentDueRule
from app.schemas.common import Money, PositiveMoney

AccountName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]


class CreditConfigCreate(BaseModel):
    credit_limit: PositiveMoney
    cutoff_day: int = Field(ge=1, le=31)
    payment_due_rule: PaymentDueRule
    # Day of the month (1-31) for fixed_day, number of days (1-60) for days_after_cutoff.
    # The range depends on the rule, so app/domain/cycles.py validates it.
    payment_due_value: int = Field(ge=1)


class AccountCreate(BaseModel):
    # Savings accounts arrive with savings mode (the default "Sobrante" one and goals)
    type: Literal[AccountType.DEBIT, AccountType.CASH, AccountType.CREDIT]
    name: AccountName
    # For a credit card, enter current debt as a negative number
    initial_balance: Money = Decimal("0.00")
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    # Required for credit accounts and rejected for the rest: without a cutoff day
    # nothing about the card can be calculated
    credit: CreditConfigCreate | None = None

    @model_validator(mode="after")
    def credit_config_matches_type(self) -> Self:
        if self.type is AccountType.CREDIT and self.credit is None:
            raise ValueError("A credit account needs its credit config")
        if self.type is not AccountType.CREDIT and self.credit is not None:
            raise ValueError(f"A {self.type} account can't have a credit config")
        return self


def _reject_explicit_nulls(model: BaseModel, fields: tuple[str, ...]) -> None:
    """Leaving a field out keeps it; sending null for one that can't be empty is an error."""
    for field in fields:
        if field in model.model_fields_set and getattr(model, field) is None:
            raise ValueError(f"{field} can't be null")


class CreditConfigUpdate(BaseModel):
    """Fields left out keep their value. The merged config is validated as a whole."""

    model_config = ConfigDict(extra="forbid")

    credit_limit: PositiveMoney | None = None
    cutoff_day: int | None = Field(default=None, ge=1, le=31)
    payment_due_rule: PaymentDueRule | None = None
    payment_due_value: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def no_explicit_nulls(self) -> Self:
        _reject_explicit_nulls(
            self, ("credit_limit", "cutoff_day", "payment_due_rule", "payment_due_value")
        )
        return self


class AccountUpdate(BaseModel):
    """Partial edit of an account. Fields left out don't change.

    The type can't change. `credit` only applies to credit accounts; changing the cutoff day
    recalculates the dates of the card's MSI installments.
    """

    # Unknown fields (type, position...) get a 422 instead of being silently ignored
    model_config = ConfigDict(extra="forbid")

    name: AccountName | None = None
    # Fixes a typo: every balance is recalculated from it
    initial_balance: Money | None = None
    # null removes the color
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    credit: CreditConfigUpdate | None = None

    @model_validator(mode="after")
    def no_explicit_nulls(self) -> Self:
        _reject_explicit_nulls(self, ("name", "initial_balance", "credit"))
        return self


class CardCycleRead(BaseModel):
    start: date
    cutoff: date
    payment_due: date


class CreditRead(BaseModel):
    credit_limit: Money
    cutoff_day: int
    payment_due_rule: PaymentDueRule
    payment_due_value: int
    # Limit - debt; the debt includes the full total of MSI purchases
    available: Money
    # Cycle that today's purchases go into
    current_cycle: CardCycleRead
    # Last closed cycle: the statement to pay next, unless its due date already passed
    last_statement: CardCycleRead


class AccountRead(BaseModel):
    id: uuid.UUID
    type: AccountType
    name: str
    initial_balance: Money
    # initial_balance + active movements. Negative on a credit card means debt.
    balance: Money
    color: str | None
    position: int
    # Only on credit accounts
    credit: CreditRead | None
