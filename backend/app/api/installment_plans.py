from fastapi import APIRouter, status

from app.api.deps import CurrentUserId, SessionDep
from app.schemas.installments import InstallmentPlanCreate, InstallmentPlanRead
from app.services import installments as installments_service

router = APIRouter(prefix="/installment-plans", tags=["installment plans"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_installment_plan(
    data: InstallmentPlanCreate, session: SessionDep, user_id: CurrentUserId
) -> InstallmentPlanRead:
    """Record a purchase in interest-free installments (MSI) on a credit card.

    Creates one expense for the total (it uses the card's credit right away) and one
    installment per month. The first one is billed in the purchase's cycle.
    """
    plan = installments_service.create_plan(session, user_id, data)
    return InstallmentPlanRead.model_validate(plan)
