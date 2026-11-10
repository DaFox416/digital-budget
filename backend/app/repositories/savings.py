"""Queries for savings mode. All of them filter by user_id."""

import uuid
from decimal import Decimal

from sqlalchemy import Subquery, func, select
from sqlalchemy.orm import Session

from app.models import Commitment, LeftoverRelease, Movement, Preferences


def _active_payment() -> Subquery:
    """Subquery: commitment id -> id of its non-deleted payment."""
    return (
        select(Movement.commitment_id, Movement.id.label("movement_id"))
        .where(Movement.commitment_id.is_not(None), Movement.deleted_at.is_(None))
        .subquery()
    )


def list_commitments(
    session: Session, user_id: uuid.UUID
) -> list[tuple[Commitment, uuid.UUID | None]]:
    """(commitment, id of its payment or None), pending ones first."""
    payment = _active_payment()
    statement = (
        select(Commitment, payment.c.movement_id)
        .outerjoin(payment, payment.c.commitment_id == Commitment.id)
        .where(Commitment.user_id == user_id)
        .order_by(
            payment.c.movement_id.is_not(None),
            Commitment.expected_on.asc().nulls_last(),
            Commitment.created_at,
        )
    )
    result: list[tuple[Commitment, uuid.UUID | None]] = []
    # mypy loses row types through session.execute() in SQLAlchemy 2.1, so annotate them here
    for row in session.execute(statement):
        commitment: Commitment = row[0]
        movement_id: uuid.UUID | None = row[1]
        result.append((commitment, movement_id))
    return result


def get_commitment(
    session: Session, user_id: uuid.UUID, commitment_id: uuid.UUID
) -> Commitment | None:
    return session.scalar(
        select(Commitment).where(Commitment.id == commitment_id, Commitment.user_id == user_id)
    )


def payment_id(session: Session, user_id: uuid.UUID, commitment_id: uuid.UUID) -> uuid.UUID | None:
    """Id of the non-deleted expense that pays the commitment, or None if it's pending."""
    return session.scalar(
        select(Movement.id).where(
            Movement.user_id == user_id,
            Movement.commitment_id == commitment_id,
            Movement.deleted_at.is_(None),
        )
    )


def commitments_pending_total(session: Session, user_id: uuid.UUID) -> Decimal:
    payment = _active_payment()
    statement = (
        select(func.coalesce(func.sum(Commitment.amount), 0))
        .outerjoin(payment, payment.c.commitment_id == Commitment.id)
        .where(Commitment.user_id == user_id, payment.c.movement_id.is_(None))
    )
    return Decimal(session.scalar(statement) or 0)


def get_preferences(session: Session, user_id: uuid.UUID) -> Preferences | None:
    return session.get(Preferences, user_id)


def leftover_released_total(session: Session, user_id: uuid.UUID) -> Decimal:
    statement = select(func.coalesce(func.sum(LeftoverRelease.amount), 0)).where(
        LeftoverRelease.user_id == user_id
    )
    return Decimal(session.scalar(statement) or 0)
