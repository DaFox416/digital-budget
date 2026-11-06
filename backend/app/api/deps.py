import uuid
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db import get_session

# Single local user until registration/login (v1). Seeded by the initial migration.
LOCAL_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def get_current_user_id() -> uuid.UUID:
    """Will read the user from the auth cookie in v1; for the demo it's always the local user."""
    return LOCAL_USER_ID


SessionDep = Annotated[Session, Depends(get_session)]
CurrentUserId = Annotated[uuid.UUID, Depends(get_current_user_id)]
