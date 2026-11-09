"""Queries for MSI installments. All of them filter by user_id."""

import uuid
from datetime import date

from sqlalchemy import select
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
