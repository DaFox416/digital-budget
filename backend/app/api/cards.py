import uuid
from datetime import date

from fastapi import APIRouter

from app.api.deps import CurrentUserId, SessionDep
from app.schemas.cards import ActiveInstallmentPlanRead, StatementInstallmentRead, StatementRead
from app.services import installments as installments_service
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


@router.get("/{account_id}/installment-plans")
def list_active_installment_plans(
    account_id: uuid.UUID, session: SessionDep, user_id: CurrentUserId
) -> list[ActiveInstallmentPlanRead]:
    """The card's MSI purchases with installments left to bill, oldest purchase first.

    Deleted purchases are left out. An installment counts as billed once its cutoff day has
    passed: on the cutoff day the cycle is still open (rule 4).
    """
    return [
        ActiveInstallmentPlanRead(
            plan_id=plan.id,
            description=plan.description,
            purchased_on=plan.purchased_on,
            total=plan.total,
            months=plan.months,
            installment_amount=plan.installments[0].amount,
            billed=progress.billed,
            remaining=progress.remaining,
            # Active plans always have one
            next_cutoff=progress.next_cutoff or plan.purchased_on,
        )
        for plan, progress in installments_service.list_active_plans(session, user_id, account_id)
    ]
