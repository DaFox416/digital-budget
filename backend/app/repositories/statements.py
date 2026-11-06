"""Queries for a credit card statement. All of them filter by user_id."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import MovementType
from app.models import Installment, InstallmentPlan, Movement


def regular_movements_total(
    session: Session, user_id: uuid.UUID, account_id: uuid.UUID, start: date, end: date
) -> Decimal:
    """Sum of signed real amounts of expenses and incomes (refunds) in [start, end].

    MSI purchases are left out: only their installments count towards a statement.
    """
    msi_movements = select(InstallmentPlan.movement_id).where(InstallmentPlan.user_id == user_id)
    statement = select(func.coalesce(func.sum(Movement.real_amount), 0)).where(
        Movement.user_id == user_id,
        Movement.account_id == account_id,
        Movement.deleted_at.is_(None),
        Movement.type.in_([MovementType.EXPENSE, MovementType.INCOME]),
        Movement.occurred_on.between(start, end),
        Movement.id.not_in(msi_movements),
    )
    return Decimal(session.scalar(statement) or 0)


def payments_total(
    session: Session, user_id: uuid.UUID, account_id: uuid.UUID, after: date, until: date
) -> Decimal:
    """Card payments received after `after` and up to `until`, inclusive."""
    statement = select(func.coalesce(func.sum(Movement.real_amount), 0)).where(
        Movement.user_id == user_id,
        Movement.account_id == account_id,
        Movement.deleted_at.is_(None),
        Movement.type == MovementType.CARD_PAYMENT,
        Movement.occurred_on > after,
        Movement.occurred_on <= until,
    )
    return Decimal(session.scalar(statement) or 0)


def installments_billed_on(
    session: Session, user_id: uuid.UUID, account_id: uuid.UUID, cutoff: date
) -> list[tuple[Installment, InstallmentPlan]]:
    """Installments of active plans billed in the cycle that closes on `cutoff`."""
    statement = (
        select(Installment, InstallmentPlan)
        .join(InstallmentPlan, Installment.plan_id == InstallmentPlan.id)
        .join(Movement, InstallmentPlan.movement_id == Movement.id)
        .where(
            Installment.user_id == user_id,
            InstallmentPlan.account_id == account_id,
            Installment.cutoff_date == cutoff,
            Movement.deleted_at.is_(None),
        )
        .order_by(InstallmentPlan.purchased_on, InstallmentPlan.created_at)
    )
    result: list[tuple[Installment, InstallmentPlan]] = []
    # mypy loses row types through session.execute() in SQLAlchemy 2.1, so annotate them here
    for row in session.execute(statement):
        installment: Installment = row[0]
        plan: InstallmentPlan = row[1]
        result.append((installment, plan))
    return result
