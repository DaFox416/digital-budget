import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import CurrentUserId, SessionDep
from app.schemas.movements import (
    MovementCreate,
    MovementRead,
    MovementUpdate,
    TransferCreate,
    TransferRead,
)
from app.services import movements as movements_service

router = APIRouter(tags=["movements"])


@router.get("/movements")
def list_movements(
    session: SessionDep,
    user_id: CurrentUserId,
    account_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[MovementRead]:
    """Non-deleted movements, newest first. Filter by account with `account_id`."""
    movements = movements_service.list_movements(session, user_id, account_id, limit)
    return [MovementRead.model_validate(movement) for movement in movements]


@router.post("/movements", status_code=status.HTTP_201_CREATED)
def create_movement(
    data: MovementCreate, session: SessionDep, user_id: CurrentUserId
) -> MovementRead:
    """Record an expense or an income. Use POST /transfers to move money between accounts."""
    movement = movements_service.create_movement(session, user_id, data)
    return MovementRead.model_validate(movement)


@router.patch("/movements/{movement_id}")
def update_movement(
    movement_id: uuid.UUID, data: MovementUpdate, session: SessionDep, user_id: CurrentUserId
) -> MovementRead:
    """Edit a movement; fields left out don't change.

    Editing either leg of a transfer or card payment changes both. MSI purchases can't be
    edited yet (409). To change the account or the type, delete and record it again.
    """
    movement = movements_service.update_movement(session, user_id, movement_id, data)
    return MovementRead.model_validate(movement)


@router.delete("/movements/{movement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_movement(
    movement_id: uuid.UUID, session: SessionDep, user_id: CurrentUserId
) -> Response:
    """Soft delete a movement; deleting either leg of a transfer deletes both.

    Undo with POST /movements/{id}/restore. Deleted movements give 404 everywhere else.
    """
    movements_service.delete_movement(session, user_id, movement_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/movements/{movement_id}/restore")
def restore_movement(
    movement_id: uuid.UUID, session: SessionDep, user_id: CurrentUserId
) -> MovementRead:
    """Undo a delete, including the other leg of a transfer. 409 if it isn't deleted."""
    movement = movements_service.restore_movement(session, user_id, movement_id)
    return MovementRead.model_validate(movement)


@router.post("/transfers", status_code=status.HTTP_201_CREATED)
def create_transfer(
    data: TransferCreate, session: SessionDep, user_id: CurrentUserId
) -> TransferRead:
    """Move money between accounts. To a credit card it's recorded as a card payment."""
    result = movements_service.create_transfer(session, user_id, data)
    return TransferRead(
        transfer_group_id=result.transfer_group_id,
        type=result.type,
        source=MovementRead.model_validate(result.source),
        destination=MovementRead.model_validate(result.destination),
    )
