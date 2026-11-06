import uuid
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.domain.enums import AccountType
from app.schemas.common import Money

AccountName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]


class AccountCreate(BaseModel):
    # Savings accounts arrive with savings mode (the default "Sobrante" one and goals)
    type: Literal[AccountType.DEBIT, AccountType.CASH, AccountType.CREDIT]
    name: AccountName
    # For a credit card, enter current debt as a negative number
    initial_balance: Money = Decimal("0.00")
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")


class AccountRead(BaseModel):
    id: uuid.UUID
    type: AccountType
    name: str
    initial_balance: Money
    # initial_balance + active movements. Negative on a credit card means debt.
    balance: Money
    color: str | None
    position: int
