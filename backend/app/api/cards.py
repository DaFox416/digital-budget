import uuid
from datetime import date

from fastapi import APIRouter

from app.api.deps import CurrentUserId, SessionDep
from app.schemas.cards import StatementInstallmentRead, StatementRead
from app.services import statements as statements_service

router = APIRouter(prefix="/cards", tags=["cards"])


@router.get("/{account_id}/statement")
def get_statement(
    account_id: uuid.UUID, session: SessionDep, user_id: CurrentUserId, cycle: date | None = None
) -> StatementRead:
    """Statement of a credit card cycle.

    `cycle` is any date in the cycle (for example its cutoff date). Without it, returns the
    last closed cycle: the one to pay next.
    """
    statement = statements_service.get_statement(session, user_id, account_id, cycle)
    return StatementRead(
        account_id=statement.account_id,
        start=statement.cycle.start,
        cutoff=statement.cycle.cutoff,
        payment_due=statement.cycle.payment_due,
        regular_charges=statement.regular_charges,
        installments_due=statement.installments_due,
        installments=[
            StatementInstallmentRead(
                plan_id=plan.id,
                description=plan.description,
                number=installment.number,
                months=plan.months,
                amount=installment.amount,
            )
            for installment, plan in statement.installments
        ],
        payments_after_cutoff=statement.payments_after_cutoff,
        payment_for_no_interest=statement.payment_for_no_interest,
    )
