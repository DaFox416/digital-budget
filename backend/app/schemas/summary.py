import uuid
from datetime import date

from pydantic import BaseModel

from app.schemas.common import Money


class NextPaymentRead(BaseModel):
    cutoff: date
    payment_due: date
    # Payment for no interest (rule 8). If `is_closed` is false it's the open cycle: the
    # previous statement is past due and this is what's been charged so far
    amount: Money
    is_closed: bool


class CardSummaryRead(BaseModel):
    account_id: uuid.UUID
    name: str
    # Includes the full total of MSI purchases; negative is a credit in your favor
    debt: Money
    # MSI installments not yet charged to "available" (they're already inside the debt)
    installments_pending: Money
    next_payment: NextPaymentRead


class SummaryRead(BaseModel):
    """Home screen figures. Savings mode figures (available, set aside, savings, leftover)
    arrive on day 10."""

    # The day the figures are calculated for (today in America/Mexico_City)
    on: date
    # Debit and cash accounts; savings accounts don't count
    real_balance: Money
    card_debt: Money
    installments_pending: Money
    cards: list[CardSummaryRead]
