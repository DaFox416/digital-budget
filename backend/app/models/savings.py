"""Savings mode tables: commitments, preferences and leftover releases."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import SavingsMode
from app.domain.savings import DEFAULT_ROUNDING_MULTIPLE, MAX_ROUNDING_MULTIPLE
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, str_enum


class Commitment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A planned expense not paid yet ("apartado"). It lowers "available" until it's paid.

    There's no status column: it's paid while a non-deleted expense references it, so
    deleting or restoring the payment can't leave it out of sync.
    """

    __tablename__ = "commitments"
    __table_args__ = (
        # Lets movements reference (id, user_id): a payment can't use another user's commitment
        UniqueConstraint("id", "user_id"),
        CheckConstraint("amount > 0", name="amount_positive"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    amount: Mapped[Decimal]
    expected_on: Mapped[date | None]


class Preferences(TimestampMixin, Base):
    """One row per user. Without a row, the defaults apply."""

    __tablename__ = "preferences"
    __table_args__ = (
        CheckConstraint(
            f"rounding_multiple BETWEEN 1 AND {MAX_ROUNDING_MULTIPLE}",
            name="rounding_multiple_in_range",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    mode: Mapped[SavingsMode] = mapped_column(
        str_enum(SavingsMode, "savings_mode"), default=SavingsMode.SIMPLE
    )
    rounding_multiple: Mapped[int] = mapped_column(SmallInteger, default=DEFAULT_ROUNDING_MULTIPLE)


class LeftoverRelease(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Leftover ("sobrante") the user moved back to "available"."""

    __tablename__ = "leftover_releases"
    __table_args__ = (CheckConstraint("amount > 0", name="amount_positive"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[Decimal]
    released_on: Mapped[date]
