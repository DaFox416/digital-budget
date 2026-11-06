import uuid
from datetime import date

from pydantic import BaseModel

from app.schemas.common import Money


class StatementInstallmentRead(BaseModel):
    plan_id: uuid.UUID
    description: str
    number: int
    months: int
    amount: Money


class StatementRead(BaseModel):
    """A credit card cycle. Amounts are positive magnitudes."""

    account_id: uuid.UUID
    start: date
    cutoff: date
    payment_due: date
    # Purchases minus refunds in the cycle, without MSI purchases
    regular_charges: Money
    # MSI installments billed in this cycle
    installments_due: Money
    installments: list[StatementInstallmentRead]
    # Card payments made after the cutoff, up to the due date
    payments_after_cutoff: Money
    # Rule 8: regular charges + installments - payments after the cutoff (never negative)
    payment_for_no_interest: Money
