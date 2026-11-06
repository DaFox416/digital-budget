import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category


def get(session: Session, user_id: uuid.UUID, category_id: uuid.UUID) -> Category | None:
    return session.scalar(
        select(Category).where(Category.id == category_id, Category.user_id == user_id)
    )


def list_all(session: Session, user_id: uuid.UUID) -> Sequence[Category]:
    return session.scalars(
        select(Category).where(Category.user_id == user_id).order_by(Category.name)
    ).all()
