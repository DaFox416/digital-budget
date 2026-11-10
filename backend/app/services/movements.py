import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.enums import MovementType
from app.domain.errors import InvalidMovementError
from app.domain.movements import (
    AccountRef,
    SignedAmounts,
    edit_amounts,
    edit_transfer_amounts,
    plan_transfer,
    signed_amounts,
)
from app.domain.savings import commitment_payment_accounting
from app.models import Account, Commitment, Movement
from app.repositories import accounts as accounts_repo
from app.repositories import categories as categories_repo
from app.repositories import movements as movements_repo
from app.repositories import savings as savings_repo
from app.schemas.movements import MovementCreate, MovementUpdate, TransferCreate
from app.services.clock import today
from app.services.errors import ConflictError, NotFoundError


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

    accounting_amount = data.accounting_amount
    if data.commitment_id is not None:
        commitment = _commitment_to_pay(session, user_id, data.type, data.commitment_id)
        if accounting_amount is None:
            accounting_amount = commitment_payment_accounting(data.amount, commitment.amount)

    amounts = signed_amounts(data.type, account.type, data.amount, accounting_amount)

    movement = Movement(
        user_id=user_id,
        account_id=account.id,
        type=data.type,
        real_amount=amounts.real_amount,
        accounting_amount=amounts.accounting_amount,
        occurred_on=data.occurred_on or today(),
        description=data.description,
        category_id=data.category_id,
        commitment_id=data.commitment_id,
    )
    session.add(movement)
    session.commit()
    return movement


def _commitment_to_pay(
    session: Session, user_id: uuid.UUID, movement_type: MovementType, commitment_id: uuid.UUID
) -> Commitment:
    if movement_type is not MovementType.EXPENSE:
        raise InvalidMovementError("Only expenses can pay a commitment")
    commitment = savings_repo.get_commitment(session, user_id, commitment_id)
    if commitment is None:
        raise NotFoundError(f"Commitment {commitment_id} not found")
    if savings_repo.payment_id(session, user_id, commitment_id) is not None:
        raise ConflictError("The commitment is already paid")
    return commitment


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


def update_movement(
    session: Session, user_id: uuid.UUID, movement_id: uuid.UUID, data: MovementUpdate
) -> Movement:
    """Edit an expense, an income or both legs of a transfer, in one transaction."""
    movement = movements_repo.get_active(session, user_id, movement_id)
    if movement is None:
        raise NotFoundError(f"Movement {movement_id} not found")
    if movements_repo.is_installment_purchase(session, user_id, movement.id):
        raise ConflictError("MSI purchases can't be edited yet")

    # Only the fields present in the request body; tells "left out" apart from an explicit null
    sent = data.model_fields_set

    if movement.transfer_group_id is not None:
        _update_transfer(session, user_id, movement, data, sent)
    else:
        _update_expense_or_income(session, user_id, movement, data, sent)

    _commit(session)
    return movement


def _reject_nulls(data: MovementUpdate, sent: set[str], fields: tuple[str, ...]) -> None:
    for field in fields:
        if field in sent and getattr(data, field) is None:
            raise InvalidMovementError(f"{field} can't be null")


def _update_expense_or_income(
    session: Session, user_id: uuid.UUID, movement: Movement, data: MovementUpdate, sent: set[str]
) -> None:
    _reject_nulls(data, sent, ("amount", "accounting_amount", "occurred_on", "description"))
    if (
        data.category_id is not None
        and categories_repo.get(session, user_id, data.category_id) is None
    ):
        raise NotFoundError(f"Category {data.category_id} not found")

    account = _get_account(session, user_id, movement.account_id)
    real = data.amount if data.amount is not None else abs(movement.real_amount)
    accounting_amount = data.accounting_amount
    commitment_id = movement.commitment_id
    if "commitment_id" in sent and data.commitment_id != movement.commitment_id:
        commitment_id = data.commitment_id
        if commitment_id is None:
            # Unlinked: like an expense created without a commitment
            if accounting_amount is None:
                accounting_amount = real
        else:
            commitment = _commitment_to_pay(session, user_id, movement.type, commitment_id)
            if accounting_amount is None:
                accounting_amount = commitment_payment_accounting(real, commitment.amount)
    elif commitment_id is not None and data.amount is not None and accounting_amount is None:
        # Like when creating: a commitment payment keeps consuming the whole commitment
        current = savings_repo.get_commitment(session, user_id, commitment_id)
        assert current is not None
        accounting_amount = commitment_payment_accounting(data.amount, current.amount)
    amounts = edit_amounts(
        movement.type,
        account.type,
        SignedAmounts(movement.real_amount, movement.accounting_amount),
        data.amount,
        accounting_amount,
    )
    movement.real_amount = amounts.real_amount
    movement.accounting_amount = amounts.accounting_amount
    movement.commitment_id = commitment_id
    if data.occurred_on is not None:
        movement.occurred_on = data.occurred_on
    if data.description is not None:
        movement.description = data.description
    if "category_id" in sent:
        movement.category_id = data.category_id


def _update_transfer(
    session: Session, user_id: uuid.UUID, movement: Movement, data: MovementUpdate, sent: set[str]
) -> None:
    not_editable = sent & {"accounting_amount", "category_id", "commitment_id"}
    if not_editable:
        fields = ", ".join(sorted(not_editable))
        raise InvalidMovementError(f"Transfers and card payments can't edit: {fields}")
    _reject_nulls(data, sent, ("amount", "occurred_on", "description"))

    assert movement.transfer_group_id is not None
    legs = movements_repo.list_transfer_legs(session, user_id, movement.transfer_group_id)

    if data.amount is not None:
        plan = edit_transfer_amounts(movement.type, data.amount)
        for leg in legs:
            # The source leg is the one money leaves (negative)
            value = plan.source_amount if leg.real_amount < 0 else plan.destination_amount
            # Transfers don't change "available": accounting equals real
            leg.real_amount = value
            leg.accounting_amount = value
    for leg in legs:
        if data.occurred_on is not None:
            leg.occurred_on = data.occurred_on
        if data.description is not None:
            leg.description = data.description


def delete_movement(session: Session, user_id: uuid.UUID, movement_id: uuid.UUID) -> None:
    """Soft delete: mark the movement (and the other leg of a transfer) as deleted.

    An MSI purchase is deleted like any expense; its plan and installments stay, and statement
    queries leave them out while the purchase is deleted, so restoring brings them back.
    """
    movement = movements_repo.get_active(session, user_id, movement_id)
    if movement is None:
        raise NotFoundError(f"Movement {movement_id} not found")

    # One timestamp for every leg, so they read as a single deletion
    deleted_at = datetime.now(UTC)
    for item in _with_transfer_legs(session, user_id, movement, include_deleted=False):
        item.deleted_at = deleted_at
    _commit(session)


def restore_movement(session: Session, user_id: uuid.UUID, movement_id: uuid.UUID) -> Movement:
    """Undo a soft delete, including the other leg of a transfer."""
    movement = movements_repo.get_any(session, user_id, movement_id)
    if movement is None:
        raise NotFoundError(f"Movement {movement_id} not found")
    if movement.deleted_at is None:
        raise ConflictError("Movement isn't deleted")
    if movement.commitment_id is not None:
        if savings_repo.get_commitment(session, user_id, movement.commitment_id) is None:
            raise ConflictError("Its commitment was deleted; restore the commitment first")
        if savings_repo.payment_id(session, user_id, movement.commitment_id) is not None:
            raise ConflictError("Another expense already paid its commitment")

    for item in _with_transfer_legs(session, user_id, movement, include_deleted=True):
        item.deleted_at = None
    _commit(session)
    return movement


def _with_transfer_legs(
    session: Session, user_id: uuid.UUID, movement: Movement, include_deleted: bool
) -> Sequence[Movement]:
    if movement.transfer_group_id is None:
        return [movement]
    return movements_repo.list_transfer_legs(
        session, user_id, movement.transfer_group_id, include_deleted=include_deleted
    )


def _commit(session: Session) -> None:
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
