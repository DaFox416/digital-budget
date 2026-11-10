"""Queries for MSI installments. All of them filter by user_id."""

import uuid
from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Installment, InstallmentPlan, Movement


def list_pending(
    session: Session, user_id: uuid.UUID, on: date
) -> list[tuple[uuid.UUID, Installment]]:
    """(card account id, installment) for installments not yet charged to "available" on `on`.

    Plans whose purchase was deleted are left out.
    """
    statement = (
        select(InstallmentPlan.account_id, Installment)
        .join(InstallmentPlan, Installment.plan_id == InstallmentPlan.id)
        .join(Movement, InstallmentPlan.movement_id == Movement.id)
        .where(
            Installment.user_id == user_id,
            Installment.charged_on > on,
            Movement.deleted_at.is_(None),
        )
    )
    result: list[tuple[uuid.UUID, Installment]] = []
    # mypy loses row types through session.execute() in SQLAlchemy 2.1, so annotate them here
    for row in session.execute(statement):
        account_id: uuid.UUID = row[0]
        installment: Installment = row[1]
        result.append((account_id, installment))
    return result


def list_plans_for_account(
    session: Session, user_id: uuid.UUID, account_id: uuid.UUID
) -> Sequence[InstallmentPlan]:
    """Every plan of a card, including those whose purchase was deleted (so restoring works).

    Installments load with each plan (selectin).
    """
    statement = select(InstallmentPlan).where(
        InstallmentPlan.user_id == user_id, InstallmentPlan.account_id == account_id
    )
    return session.scalars(statement).all()


def charged_accounting_total(session: Session, user_id: uuid.UUID, on: date) -> Decimal:
    """Accounting amounts of installments already charged to "available" on `on`.

    Plans whose purchase was deleted are left out.
    """
    statement = (
        select(func.coalesce(func.sum(Installment.accounting_amount), 0))
        .join(InstallmentPlan, Installment.plan_id == InstallmentPlan.id)
        .join(Movement, InstallmentPlan.movement_id == Movement.id)
        .where(
            Installment.user_id == user_id,
            Installment.charged_on <= on,
            Movement.deleted_at.is_(None),
        )
    )
    return Decimal(session.scalar(statement) or 0)
