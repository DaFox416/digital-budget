import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import PaymentDueRule
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, str_enum

if TYPE_CHECKING:
    from app.models.account import Account


class CreditConfig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Limit, cutoff day and payment due rule of a credit account (one to one)."""

    __tablename__ = "credit_configs"
    __table_args__ = (
        # The account must belong to the same user as the config
        ForeignKeyConstraint(["account_id", "user_id"], ["accounts.id", "accounts.user_id"]),
        # Last line of defense for rules that also live in app/domain/cycles.py
        CheckConstraint("credit_limit > 0", name="credit_limit_positive"),
        CheckConstraint("cutoff_day BETWEEN 1 AND 31", name="cutoff_day_in_range"),
        CheckConstraint(
            "(payment_due_rule = 'fixed_day' AND payment_due_value BETWEEN 1 AND 31)"
            " OR (payment_due_rule = 'days_after_cutoff' AND payment_due_value BETWEEN 1 AND 60)",
            name="payment_due_value_in_range",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    account_id: Mapped[uuid.UUID] = mapped_column(unique=True)
    credit_limit: Mapped[Decimal]
    cutoff_day: Mapped[int] = mapped_column(SmallInteger)
    payment_due_rule: Mapped[PaymentDueRule] = mapped_column(
        str_enum(PaymentDueRule, "payment_due_rule")
    )
    # Day of the month for fixed_day, number of days for days_after_cutoff
    payment_due_value: Mapped[int] = mapped_column(SmallInteger)

    account: Mapped["Account"] = relationship(back_populates="credit_config")
