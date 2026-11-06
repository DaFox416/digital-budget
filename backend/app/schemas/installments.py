import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.domain.installments import MAX_MONTHS, MIN_MONTHS
from app.schemas.common import Money, PositiveMoney
from app.schemas.movements import Description


class InstallmentPlanCreate(BaseModel):
    """A purchase in interest-free installments (MSI) on a credit card."""

    account_id: uuid.UUID
    total: PositiveMoney
    # The frontend offers 3, 6, 9 and 12 first; any value in range is accepted
    months: int = Field(ge=MIN_MONTHS, le=MAX_MONTHS)
    # Defaults to today in the configured time zone (America/Mexico_City)
    purchased_on: date | None = None
    description: Description = ""
    category_id: uuid.UUID | None = None


class InstallmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    number: int
    amount: Money
    accounting_amount: Money
    # Cutoff of the statement it's billed in
    cutoff_date: date
    # When it reduces "available"
    charged_on: date


class InstallmentPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    # The expense for the total (real = -total, accounting = 0)
    movement_id: uuid.UUID
    total: Money
    months: int
    purchased_on: date
    description: str
    installments: list[InstallmentRead]
