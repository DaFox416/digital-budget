import uuid

from fastapi import APIRouter, status

from app.api.deps import CurrentUserId, SessionDep
from app.schemas.savings import (
    CommitmentCreate,
    CommitmentRead,
    CommitmentUpdate,
    LeftoverReleaseCreate,
    LeftoverReleaseRead,
    PreferencesRead,
    PreferencesUpdate,
)
from app.services import savings as savings_service
from app.services.savings import CommitmentWithPayment

router = APIRouter(tags=["savings mode"])


def _commitment_read(item: CommitmentWithPayment) -> CommitmentRead:
    return CommitmentRead(
        id=item.commitment.id,
        name=item.commitment.name,
        amount=item.commitment.amount,
        expected_on=item.commitment.expected_on,
        paid_by_movement_id=item.paid_by_movement_id,
    )


@router.get("/commitments")
def list_commitments(session: SessionDep, user_id: CurrentUserId) -> list[CommitmentRead]:
    """Commitments ("apartados"), pending ones first by expected date."""
    return [_commitment_read(item) for item in savings_service.list_commitments(session, user_id)]


@router.post("/commitments", status_code=status.HTTP_201_CREATED)
def create_commitment(
    data: CommitmentCreate, session: SessionDep, user_id: CurrentUserId
) -> CommitmentRead:
    return _commitment_read(savings_service.create_commitment(session, user_id, data))


@router.patch("/commitments/{commitment_id}")
def update_commitment(
    commitment_id: uuid.UUID, data: CommitmentUpdate, session: SessionDep, user_id: CurrentUserId
) -> CommitmentRead:
    """Edit a pending commitment. A paid one answers 409."""
    return _commitment_read(
        savings_service.update_commitment(session, user_id, commitment_id, data)
    )


@router.get("/preferences")
def get_preferences(session: SessionDep, user_id: CurrentUserId) -> PreferencesRead:
    preferences = savings_service.get_preferences(session, user_id)
    return PreferencesRead(mode=preferences.mode, rounding_multiple=preferences.rounding_multiple)


@router.patch("/preferences")
def update_preferences(
    data: PreferencesUpdate, session: SessionDep, user_id: CurrentUserId
) -> PreferencesRead:
    """Savings mode on or off and the rounding multiple. The mode only changes what the app
    shows: both amounts are always stored."""
    preferences = savings_service.update_preferences(session, user_id, data)
    return PreferencesRead(mode=preferences.mode, rounding_multiple=preferences.rounding_multiple)


@router.post("/leftover-releases", status_code=status.HTTP_201_CREATED)
def release_leftover(
    data: LeftoverReleaseCreate, session: SessionDep, user_id: CurrentUserId
) -> LeftoverReleaseRead:
    """Move leftover ("sobrante") back to "available", in multiples of the rounding."""
    release = savings_service.release_leftover(session, user_id, data)
    return LeftoverReleaseRead.model_validate(release)
