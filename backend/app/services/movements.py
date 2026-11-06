import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.enums import MovementType
from app.domain.movements import AccountRef, plan_transfer, signed_amounts
from app.models import Account, Movement
from app.repositories import accounts as accounts_repo
from app.repositories import categories as categories_repo
from app.repositories import movements as movements_repo
from app.schemas.movements import MovementCreate, TransferCreate
from app.services.clock import today
from app.services.errors import NotFoundError


@dataclass(frozen=True)
class TransferResult:
    transfer_group_id: uuid.UUID
    type: MovementType
    source: Movement
    destination: Movement


def _get_account(session: Session, user_id: uuid.UUID, account_id: uuid.UUID) -> Account:
    account = accounts_repo.get(session, user_id, account_id)
    if account is None:
        raise NotFoundError(f"Account {account_id} not found")
    return account


def list_movements(
    session: Session, user_id: uuid.UUID, account_id: uuid.UUID | None = None, limit: int = 100
) -> Sequence[Movement]:
    return movements_repo.list_active(session, user_id, account_id, limit)


def create_movement(session: Session, user_id: uuid.UUID, data: MovementCreate) -> Movement:
    account = _get_account(session, user_id, data.account_id)
    if (
        data.category_id is not None
        and categories_repo.get(session, user_id, data.category_id) is None
    ):
        raise NotFoundError(f"Category {data.category_id} not found")

    amounts = signed_amounts(data.type, account.type, data.amount, data.accounting_amount)

    movement = Movement(
        user_id=user_id,
        account_id=account.id,
        type=data.type,
        real_amount=amounts.real_amount,
        accounting_amount=amounts.accounting_amount,
        occurred_on=data.occurred_on or today(),
        description=data.description,
        category_id=data.category_id,
    )
    session.add(movement)
    session.commit()
    return movement


def create_transfer(session: Session, user_id: uuid.UUID, data: TransferCreate) -> TransferResult:
    """Create both legs of a transfer in a single database transaction."""
    source = _get_account(session, user_id, data.source_account_id)
    destination = _get_account(session, user_id, data.destination_account_id)

    plan = plan_transfer(
        AccountRef(source.id, source.type),
        AccountRef(destination.id, destination.type),
        data.amount,
    )

    group_id = uuid.uuid4()
    occurred_on = data.occurred_on or today()

    def leg(account: Account, amount_value: Decimal) -> Movement:
        return Movement(
            user_id=user_id,
            account_id=account.id,
            type=plan.movement_type,
            real_amount=amount_value,
            # Transfers don't change "available": accounting equals real
            accounting_amount=amount_value,
            occurred_on=occurred_on,
            description=data.description,
            transfer_group_id=group_id,
        )

    outgoing = leg(source, plan.source_amount)
    incoming = leg(destination, plan.destination_amount)

    session.add_all([outgoing, incoming])
    try:
        # One commit for both rows: Postgres saves both or neither
        session.commit()
    except Exception:
        session.rollback()
        raise

    return TransferResult(group_id, plan.movement_type, outgoing, incoming)
