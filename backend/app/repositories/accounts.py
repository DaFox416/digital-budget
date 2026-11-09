import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, Movement


def get(session: Session, user_id: uuid.UUID, account_id: uuid.UUID) -> Account | None:
    return session.scalar(
        select(Account).where(Account.id == account_id, Account.user_id == user_id)
    )


def get_by_name(session: Session, user_id: uuid.UUID, name: str) -> Account | None:
    return session.scalar(select(Account).where(Account.user_id == user_id, Account.name == name))


def count(session: Session, user_id: uuid.UUID) -> int:
    return session.scalar(select(func.count()).where(Account.user_id == user_id)) or 0


def list_with_movement_totals(
    session: Session, user_id: uuid.UUID
) -> list[tuple[Account, Decimal]]:
    """Active accounts with the sum of real amounts of their non-deleted movements.

    One query for all accounts: the totals are aggregated in Postgres.
    """
    totals = (
        select(Movement.account_id, func.sum(Movement.real_amount).label("total"))
        .where(Movement.user_id == user_id, Movement.deleted_at.is_(None))
        .group_by(Movement.account_id)
        .subquery()
    )
    statement = (
        select(Account, func.coalesce(totals.c.total, 0))
        .outerjoin(totals, totals.c.account_id == Account.id)
        .where(Account.user_id == user_id, Account.archived_at.is_(None))
        .order_by(Account.position, Account.created_at)
    )
    result: list[tuple[Account, Decimal]] = []
    # mypy loses row types through session.execute() in SQLAlchemy 2.1, so annotate them here
    for row in session.execute(statement):
        account: Account = row[0]
        total: Decimal = row[1]
        result.append((account, total))
    return result


def movements_total(session: Session, user_id: uuid.UUID, account_id: uuid.UUID) -> Decimal:
    """Sum of real amounts of the account's non-deleted movements."""
    statement = select(func.coalesce(func.sum(Movement.real_amount), 0)).where(
        Movement.user_id == user_id,
        Movement.account_id == account_id,
        Movement.deleted_at.is_(None),
    )
    return Decimal(session.scalar(statement) or 0)
