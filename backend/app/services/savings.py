"""Savings mode use cases: the seven figures, commitments, preferences and leftover releases."""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.enums import SavingsMode
from app.domain.errors import InvalidCommitmentError
from app.domain.savings import (
    DEFAULT_ROUNDING_MULTIPLE,
    AccountTotals,
    SavingsFigures,
    SavingsInputs,
    releasable_leftover,
    savings_figures,
    validate_leftover_release,
    validate_rounding_multiple,
)
from app.models import Commitment, LeftoverRelease, Preferences
from app.repositories import accounts as accounts_repo
from app.repositories import installments as installments_repo
from app.repositories import savings as savings_repo
from app.schemas.savings import (
    CommitmentCreate,
    CommitmentUpdate,
    LeftoverReleaseCreate,
    PreferencesUpdate,
)
from app.services.accounts import list_accounts
from app.services.clock import today
from app.services.errors import ConflictError, NotFoundError


@dataclass(frozen=True)
class Figures:
    figures: SavingsFigures
    # How much leftover can go back to "available" (whole multiples of the rounding)
    leftover_releasable: Decimal


@dataclass(frozen=True)
class CommitmentWithPayment:
    commitment: Commitment
    paid_by_movement_id: uuid.UUID | None


# --- Figures ---


def current_figures(session: Session, user_id: uuid.UUID, on: date) -> Figures:
    accounting = accounts_repo.accounting_totals(session, user_id)
    accounts = [
        AccountTotals(
            type=item.account.type,
            balance=item.balance,
            accounting_balance=item.account.initial_balance
            + accounting.get(item.account.id, Decimal("0")),
        )
        for item in list_accounts(session, user_id)
    ]
    pending = sum(
        (item.amount for _, item in installments_repo.list_pending(session, user_id, on)),
        Decimal("0"),
    )
    figures = savings_figures(
        SavingsInputs(
            accounts=accounts,
            installments_charged_accounting=installments_repo.charged_accounting_total(
                session, user_id, on
            ),
            installments_pending=pending,
            commitments_pending=savings_repo.commitments_pending_total(session, user_id),
            leftover_released=savings_repo.leftover_released_total(session, user_id),
        )
    )
    multiple = get_preferences(session, user_id).rounding_multiple
    return Figures(figures, releasable_leftover(figures.leftover, multiple))


# --- Preferences ---


def get_preferences(session: Session, user_id: uuid.UUID) -> Preferences:
    """The saved preferences, or the defaults (not saved) if the user never changed them."""
    preferences = savings_repo.get_preferences(session, user_id)
    if preferences is None:
        return Preferences(
            user_id=user_id,
            mode=SavingsMode.SIMPLE,
            rounding_multiple=DEFAULT_ROUNDING_MULTIPLE,
        )
    return preferences


def update_preferences(
    session: Session, user_id: uuid.UUID, data: PreferencesUpdate
) -> Preferences:
    preferences = get_preferences(session, user_id)
    if data.rounding_multiple is not None:
        preferences.rounding_multiple = validate_rounding_multiple(data.rounding_multiple)
    if data.mode is not None:
        preferences.mode = data.mode
    session.add(preferences)
    session.commit()
    return preferences


# --- Leftover ---


def release_leftover(
    session: Session, user_id: uuid.UUID, data: LeftoverReleaseCreate
) -> LeftoverRelease:
    on = today()
    current = current_figures(session, user_id, on)
    multiple = get_preferences(session, user_id).rounding_multiple
    amount = validate_leftover_release(data.amount, current.figures.leftover, multiple)

    release = LeftoverRelease(user_id=user_id, amount=amount, released_on=on)
    session.add(release)
    session.commit()
    return release


def undo_leftover_release(session: Session, user_id: uuid.UUID, release_id: uuid.UUID) -> None:
    """Soft delete a release: its amount goes back from "available" to the leftover. Always
    allowed, since it only makes the leftover grow."""
    release = savings_repo.get_leftover_release(session, user_id, release_id)
    if release is None:
        raise NotFoundError(f"Leftover release {release_id} not found")
    release.deleted_at = datetime.now(UTC)
    session.commit()


# --- Commitments ---


def list_commitments(session: Session, user_id: uuid.UUID) -> list[CommitmentWithPayment]:
    return [
        CommitmentWithPayment(commitment, paid_by)
        for commitment, paid_by in savings_repo.list_commitments(session, user_id)
    ]


def create_commitment(
    session: Session, user_id: uuid.UUID, data: CommitmentCreate
) -> CommitmentWithPayment:
    commitment = Commitment(
        user_id=user_id, name=data.name, amount=data.amount, expected_on=data.expected_on
    )
    session.add(commitment)
    session.commit()
    return CommitmentWithPayment(commitment, None)


def get_commitment(session: Session, user_id: uuid.UUID, commitment_id: uuid.UUID) -> Commitment:
    commitment = savings_repo.get_commitment(session, user_id, commitment_id)
    if commitment is None:
        raise NotFoundError(f"Commitment {commitment_id} not found")
    return commitment


def update_commitment(
    session: Session, user_id: uuid.UUID, commitment_id: uuid.UUID, data: CommitmentUpdate
) -> CommitmentWithPayment:
    commitment = get_commitment(session, user_id, commitment_id)
    if savings_repo.payment_id(session, user_id, commitment.id) is not None:
        raise ConflictError("A paid commitment can't be edited")

    sent = data.model_fields_set
    for field in ("name", "amount"):
        if field in sent and getattr(data, field) is None:
            raise InvalidCommitmentError(f"{field} can't be null")
    if data.name is not None:
        commitment.name = data.name
    if data.amount is not None:
        commitment.amount = data.amount
    if "expected_on" in sent:
        commitment.expected_on = data.expected_on
    session.commit()
    return CommitmentWithPayment(commitment, None)


def delete_commitment(session: Session, user_id: uuid.UUID, commitment_id: uuid.UUID) -> None:
    """Soft delete a pending commitment. A paid one answers 409: delete its payment first, so
    no expense points to a deleted commitment."""
    commitment = get_commitment(session, user_id, commitment_id)
    if savings_repo.payment_id(session, user_id, commitment.id) is not None:
        raise ConflictError("A paid commitment can't be deleted; delete its payment first")
    commitment.deleted_at = datetime.now(UTC)
    session.commit()


def restore_commitment(
    session: Session, user_id: uuid.UUID, commitment_id: uuid.UUID
) -> CommitmentWithPayment:
    commitment = savings_repo.get_commitment(session, user_id, commitment_id, include_deleted=True)
    if commitment is None:
        raise NotFoundError(f"Commitment {commitment_id} not found")
    if commitment.deleted_at is None:
        raise ConflictError("Commitment isn't deleted")
    commitment.deleted_at = None
    session.commit()
    # Deleting required it to be pending, and a deleted commitment can't be paid
    return CommitmentWithPayment(commitment, None)
