from fastapi import APIRouter

from app.api.deps import CurrentUserId, SessionDep
from app.schemas.summary import CardSummaryRead, NextPaymentRead, SummaryRead
from app.services import summary as summary_service

router = APIRouter(tags=["summary"])


@router.get("/summary")
def get_summary(session: SessionDep, user_id: CurrentUserId) -> SummaryRead:
    """Real balance, card debt, MSI pending to charge and the next payment of each card."""
    summary = summary_service.get_summary(session, user_id)
    return SummaryRead(
        on=summary.on,
        real_balance=summary.real_balance,
        card_debt=summary.card_debt,
        installments_pending=summary.installments_pending,
        cards=[
            CardSummaryRead(
                account_id=card.account_id,
                name=card.name,
                debt=card.debt,
                installments_pending=card.installments_pending,
                next_payment=NextPaymentRead(
                    cutoff=card.next_payment.cycle.cutoff,
                    payment_due=card.next_payment.cycle.payment_due,
                    amount=card.next_payment.amount,
                    is_closed=card.next_payment.is_closed,
                ),
            )
            for card in summary.cards
        ],
    )
