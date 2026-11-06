import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Movement


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
