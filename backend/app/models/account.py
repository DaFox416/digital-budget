import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import AccountType
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, str_enum


class Account(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("user_id", "name"),
        # Lets movements reference (id, user_id): a movement can't use another user's account
        UniqueConstraint("id", "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[AccountType] = mapped_column(str_enum(AccountType, "account_type"))
    name: Mapped[str] = mapped_column(String(60))
    initial_balance: Mapped[Decimal] = mapped_column(default=Decimal("0.00"))
    color: Mapped[str | None] = mapped_column(String(7))
    position: Mapped[int] = mapped_column(default=0)
    archived_at: Mapped[datetime | None]
