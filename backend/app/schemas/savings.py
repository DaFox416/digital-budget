import uuid
from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.domain.enums import SavingsMode
from app.domain.savings import MAX_ROUNDING_MULTIPLE
from app.schemas.common import Money, PositiveMoney

CommitmentName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)
]


class CommitmentCreate(BaseModel):
    """A planned expense ("apartado"), like the electricity bill. It lowers "available" until
    an expense pays it (send its id as `commitment_id` when recording the expense)."""

    name: CommitmentName
    amount: PositiveMoney
    expected_on: date | None = None


class CommitmentUpdate(BaseModel):
    """Partial edit; fields left out don't change. A paid commitment can't be edited."""

    model_config = ConfigDict(extra="forbid")

    name: CommitmentName | None = None
    amount: PositiveMoney | None = None
    # null removes the date
    expected_on: date | None = None


class CommitmentRead(BaseModel):
    id: uuid.UUID
    name: str
    amount: Money
    expected_on: date | None
    # The non-deleted expense that paid it; null while it's pending
    paid_by_movement_id: uuid.UUID | None


class PreferencesRead(BaseModel):
    mode: SavingsMode
    # Savings mode proposes accounting amounts rounded to this multiple (in pesos)
    rounding_multiple: int


class PreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: SavingsMode | None = None
    rounding_multiple: int | None = Field(default=None, ge=1, le=MAX_ROUNDING_MULTIPLE)


class LeftoverReleaseCreate(BaseModel):
    """Move leftover ("sobrante") back to "available". It must be a multiple of the rounding
    and no more than the leftover; `GET /summary` says how much can be released."""

    amount: PositiveMoney


class LeftoverReleaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    amount: Money
    released_on: date
