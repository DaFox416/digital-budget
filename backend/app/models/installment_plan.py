import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class InstallmentPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A purchase in interest-free installments (MSI) on a credit card.

    The purchase itself is one expense movement for the total (real = -total, accounting = 0):
    it uses the card's credit right away. Each installment reduces "available" on its own date.
    """

    __tablename__ = "installment_plans"
    __table_args__ = (
        # Card and movement must belong to the same user as the plan
        ForeignKeyConstraint(["account_id", "user_id"], ["accounts.id", "accounts.user_id"]),
        ForeignKeyConstraint(["movement_id", "user_id"], ["movements.id", "movements.user_id"]),
        UniqueConstraint("id", "user_id"),
        # Last line of defense for rules that also live in app/domain/installments.py
        CheckConstraint("total > 0", name="total_positive"),
        CheckConstraint("months BETWEEN 3 AND 48", name="months_in_range"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    account_id: Mapped[uuid.UUID] = mapped_column(index=True)
    # The expense for the total; one plan per movement
    movement_id: Mapped[uuid.UUID] = mapped_column(unique=True)
    total: Mapped[Decimal]
    months: Mapped[int] = mapped_column(SmallInteger)
    purchased_on: Mapped[date]
    description: Mapped[str] = mapped_column(String(200), default="")

    installments: Mapped[list["Installment"]] = relationship(
        back_populates="plan",
        lazy="selectin",
        order_by="Installment.number",
        cascade="all, delete-orphan",
    )


class Installment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One monthly installment of a plan. Not a movement: no money moves when it's charged."""

    __tablename__ = "installments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["plan_id", "user_id"], ["installment_plans.id", "installment_plans.user_id"]
        ),
        UniqueConstraint("plan_id", "number"),
        CheckConstraint("number BETWEEN 1 AND 48", name="number_in_range"),
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("accounting_amount >= 0", name="accounting_amount_not_negative"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    plan_id: Mapped[uuid.UUID] = mapped_column(index=True)
    number: Mapped[int] = mapped_column(SmallInteger)
    # Positive magnitudes: what's billed and what reduces "available" (savings mode rounding)
    amount: Mapped[Decimal]
    accounting_amount: Mapped[Decimal]
    # Cutoff of the statement it's billed in
    cutoff_date: Mapped[date] = mapped_column(index=True)
    # When it reduces "available": purchase date for the first one, cycle start for the rest
    charged_on: Mapped[date]

    plan: Mapped[InstallmentPlan] = relationship(back_populates="installments")
