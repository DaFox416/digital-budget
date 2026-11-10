import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import MovementType
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, str_enum

_TRANSFER_TYPES_SQL = "type IN ('transfer', 'card_payment')"


class Movement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "movements"
    __table_args__ = (
        # The account and category must belong to the same user as the movement
        ForeignKeyConstraint(["account_id", "user_id"], ["accounts.id", "accounts.user_id"]),
        ForeignKeyConstraint(["category_id", "user_id"], ["categories.id", "categories.user_id"]),
        ForeignKeyConstraint(
            ["commitment_id", "user_id"], ["commitments.id", "commitments.user_id"]
        ),
        # Lets installment plans reference (id, user_id)
        UniqueConstraint("id", "user_id"),
        # Last line of defense for rules that also live in app/domain
        CheckConstraint("real_amount <> 0", name="real_amount_not_zero"),
        CheckConstraint(
            f"({_TRANSFER_TYPES_SQL}) = (transfer_group_id IS NOT NULL)",
            name="transfer_group_matches_type",
        ),
        CheckConstraint(
            f"NOT ({_TRANSFER_TYPES_SQL}) OR accounting_amount = real_amount",
            name="transfer_amounts_equal",
        ),
        CheckConstraint(
            "commitment_id IS NULL OR type = 'expense'", name="commitment_only_on_expenses"
        ),
        Index("ix_movements_user_id_occurred_on", "user_id", "occurred_on"),
        # A commitment has at most one non-deleted payment
        Index(
            "uq_movements_active_commitment_id",
            "commitment_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    account_id: Mapped[uuid.UUID] = mapped_column(index=True)
    type: Mapped[MovementType] = mapped_column(str_enum(MovementType, "movement_type"))
    # Signed: negative when money leaves the account, positive when it enters
    real_amount: Mapped[Decimal]
    accounting_amount: Mapped[Decimal]
    occurred_on: Mapped[date]
    description: Mapped[str] = mapped_column(String(200), default="")
    category_id: Mapped[uuid.UUID | None]
    # Links the two movements of a transfer or card payment
    transfer_group_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    # The commitment ("apartado") this expense pays
    commitment_id: Mapped[uuid.UUID | None]
    # Soft delete: movements are never physically deleted
    deleted_at: Mapped[datetime | None]
