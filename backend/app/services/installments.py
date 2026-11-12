import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.balances import check_credit_limit
from app.domain.enums import MovementType, SavingsMode
from app.domain.installments import installment_schedule, validate_installment_account
from app.domain.money import to_money
from app.domain.savings import installment_accounting
from app.models import Installment, InstallmentPlan, Movement
from app.repositories import accounts as accounts_repo
from app.repositories import categories as categories_repo
from app.schemas.installments import InstallmentPlanCreate
from app.services import savings as savings_service
from app.services.accounts import current_credit_available, cycle_config
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
    # The whole total uses the card's credit today
    check_credit_limit(total, current_credit_available(session, user_id, account))
    schedule = installment_schedule(
        total, data.months, purchased_on, cycle_config(account.credit_config)
    )
    # Savings mode rounds each installment up to the multiple (the difference goes to the
    # leftover); simple mode keeps accounting equal to real. The mode at purchase time counts
    preferences = savings_service.get_preferences(session, user_id)
    rounding = preferences.rounding_multiple if preferences.mode is SavingsMode.SAVINGS else None

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
                accounting_amount=(
                    item.amount
                    if rounding is None
                    else installment_accounting(item.amount, rounding)
                ),
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
