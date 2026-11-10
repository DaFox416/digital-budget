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
    """The seven savings mode figures (always sent; simple mode just shows fewer).

    real_balance = available + set_aside + card_debt + savings_goals + leftover
                   - installments_pending
    """

    # The day the figures are calculated for (today in America/Mexico_City)
    on: date
    # Debit and cash accounts; savings accounts don't count
    real_balance: Money
    # What you can spend without touching what's set aside, saved or owed
    available: Money
    # Commitments ("apartados") not paid yet
    set_aside: Money
    card_debt: Money
    # Savings goals arrive in v1; always 0 for now
    savings_goals: Money
    # Differences between real and accounting amounts ("sobrante")
    leftover: Money
    # How much leftover can go back to "available" (multiples of the rounding)
    leftover_releasable: Money
    # MSI installments not yet charged to "available" (they're already inside the debt)
    installments_pending: Money
    cards: list[CardSummaryRead]
