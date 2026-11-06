import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.domain.enums import MovementType
from app.schemas.common import Money, NonNegativeMoney, PositiveMoney

Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]


class MovementCreate(BaseModel):
    """An expense or an income. Amounts are positive; the type decides the sign."""

    account_id: uuid.UUID
    type: Literal[MovementType.EXPENSE, MovementType.INCOME]
    amount: PositiveMoney
    # Savings mode only; defaults to `amount`
    accounting_amount: NonNegativeMoney | None = None
    # Defaults to today in the configured time zone (America/Mexico_City)
    occurred_on: date | None = None
    description: Description = ""
    category_id: uuid.UUID | None = None


class TransferCreate(BaseModel):
    """Move money between accounts. To a credit card it's recorded as a card payment."""

    source_account_id: uuid.UUID
    destination_account_id: uuid.UUID
    amount: PositiveMoney
    occurred_on: date | None = None
    description: Description = ""


class MovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    type: MovementType
    # Signed: negative when money leaves the account
    real_amount: Money
    accounting_amount: Money
    occurred_on: date
    description: str
    category_id: uuid.UUID | None
    transfer_group_id: uuid.UUID | None
    created_at: datetime


class TransferRead(BaseModel):
    transfer_group_id: uuid.UUID
    type: MovementType
    source: MovementRead
    destination: MovementRead
