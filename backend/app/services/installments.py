import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.enums import MovementType
from app.domain.installments import installment_schedule, validate_installment_account
from app.domain.money import to_money
from app.models import Installment, InstallmentPlan, Movement
from app.repositories import accounts as accounts_repo
from app.repositories import categories as categories_repo
from app.schemas.installments import InstallmentPlanCreate
from app.services.accounts import cycle_config
from app.services.clock import today
from app.services.errors import NotFoundError


def create_plan(
    session: Session, user_id: uuid.UUID, data: InstallmentPlanCreate
) -> InstallmentPlan:
    """Create the expense for the total, the plan and its installments in one transaction."""
    account = accounts_repo.get(session, user_id, data.account_id)
    if account is None:
        raise NotFoundError(f"Account {data.account_id} not found")
    validate_installment_account(account.type)
    if (
        data.category_id is not None
        and categories_repo.get(session, user_id, data.category_id) is None
    ):
        raise NotFoundError(f"Category {data.category_id} not found")
    # Credit accounts always have one (it's required when they're created)
    assert account.credit_config is not None

    purchased_on = data.purchased_on or today()
    total = to_money(data.total)
    schedule = installment_schedule(
        total, data.months, purchased_on, cycle_config(account.credit_config)
    )

    movement = Movement(
        id=uuid.uuid4(),
        user_id=user_id,
        account_id=account.id,
        type=MovementType.EXPENSE,
        # The whole purchase uses the card's credit now...
        real_amount=-total,
        # ...but "available" goes down one installment at a time, so the purchase itself is 0
        accounting_amount=Decimal("0.00"),
        occurred_on=purchased_on,
        description=data.description,
        category_id=data.category_id,
    )
    plan = InstallmentPlan(
        user_id=user_id,
        account_id=account.id,
        movement_id=movement.id,
        total=total,
        months=data.months,
        purchased_on=purchased_on,
        description=data.description,
        installments=[
            Installment(
                user_id=user_id,
                number=item.number,
                amount=item.amount,
                # Equal to the amount until savings mode rounding arrives (day 10)
                accounting_amount=item.amount,
                cutoff_date=item.cutoff,
                charged_on=item.charged_on,
            )
            for item in schedule
        ],
    )
    try:
        session.add(movement)
        # The plan references the movement, so the movement row must be inserted first
        session.flush()
        session.add(plan)
        # One commit: the expense, the plan and its installments are saved together or not at all
        session.commit()
    except Exception:
        session.rollback()
        raise
    return plan
