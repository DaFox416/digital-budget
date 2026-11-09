import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InstallmentPlan, Movement


def list_active(
    session: Session, user_id: uuid.UUID, account_id: uuid.UUID | None, limit: int
) -> Sequence[Movement]:
    """Non-deleted movements, newest first."""
    statement = select(Movement).where(Movement.user_id == user_id, Movement.deleted_at.is_(None))
    if account_id is not None:
        statement = statement.where(Movement.account_id == account_id)
    statement = statement.order_by(
        Movement.occurred_on.desc(), Movement.created_at.desc(), Movement.id
    ).limit(limit)
    return session.scalars(statement).all()


def get_active(session: Session, user_id: uuid.UUID, movement_id: uuid.UUID) -> Movement | None:
    """A non-deleted movement of the user, or None."""
    statement = select(Movement).where(
        Movement.id == movement_id, Movement.user_id == user_id, Movement.deleted_at.is_(None)
    )
    return session.scalar(statement)


def list_transfer_legs(
    session: Session, user_id: uuid.UUID, transfer_group_id: uuid.UUID
) -> Sequence[Movement]:
    """Both non-deleted legs of a transfer or card payment."""
    statement = select(Movement).where(
        Movement.user_id == user_id,
        Movement.transfer_group_id == transfer_group_id,
        Movement.deleted_at.is_(None),
    )
    return session.scalars(statement).all()


def is_installment_purchase(session: Session, user_id: uuid.UUID, movement_id: uuid.UUID) -> bool:
    """Whether the movement is the expense for the total of an MSI purchase."""
    statement = select(InstallmentPlan.id).where(
        InstallmentPlan.user_id == user_id, InstallmentPlan.movement_id == movement_id
    )
    return session.scalar(statement) is not None
