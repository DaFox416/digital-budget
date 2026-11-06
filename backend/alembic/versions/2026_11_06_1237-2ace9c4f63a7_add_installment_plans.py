"""Add installment_plans and installments (MSI).

Revision ID: 2ace9c4f63a7
Revises: 5c7b1632cdff
Create Date: 2026-11-06 12:37:00.835135

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2ace9c4f63a7"
down_revision: str | Sequence[str] | None = "5c7b1632cdff"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Must exist before installment_plans references movements (id, user_id)
    op.create_unique_constraint(op.f("uq_movements_id_user_id"), "movements", ["id", "user_id"])
    op.create_table(
        "installment_plans",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("movement_id", sa.Uuid(), nullable=False),
        sa.Column("total", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("months", sa.SmallInteger(), nullable=False),
        sa.Column("purchased_on", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "months BETWEEN 3 AND 48", name=op.f("ck_installment_plans_months_in_range")
        ),
        sa.CheckConstraint("total > 0", name=op.f("ck_installment_plans_total_positive")),
        sa.ForeignKeyConstraint(
            ["account_id", "user_id"],
            ["accounts.id", "accounts.user_id"],
            name=op.f("fk_installment_plans_account_id_user_id_accounts"),
        ),
        sa.ForeignKeyConstraint(
            ["movement_id", "user_id"],
            ["movements.id", "movements.user_id"],
            name=op.f("fk_installment_plans_movement_id_user_id_movements"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_installment_plans_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_installment_plans")),
        sa.UniqueConstraint("id", "user_id", name=op.f("uq_installment_plans_id_user_id")),
        sa.UniqueConstraint("movement_id", name=op.f("uq_installment_plans_movement_id")),
    )
    op.create_index(
        op.f("ix_installment_plans_account_id"), "installment_plans", ["account_id"], unique=False
    )
    op.create_table(
        "installments",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.SmallInteger(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("accounting_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("cutoff_date", sa.Date(), nullable=False),
        sa.Column("charged_on", sa.Date(), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "accounting_amount >= 0", name=op.f("ck_installments_accounting_amount_not_negative")
        ),
        sa.CheckConstraint("amount > 0", name=op.f("ck_installments_amount_positive")),
        sa.CheckConstraint("number BETWEEN 1 AND 48", name=op.f("ck_installments_number_in_range")),
        sa.ForeignKeyConstraint(
            ["plan_id", "user_id"],
            ["installment_plans.id", "installment_plans.user_id"],
            name=op.f("fk_installments_plan_id_user_id_installment_plans"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_installments_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_installments")),
        sa.UniqueConstraint("plan_id", "number", name=op.f("uq_installments_plan_id_number")),
    )
    op.create_index(
        op.f("ix_installments_cutoff_date"), "installments", ["cutoff_date"], unique=False
    )
    op.create_index(op.f("ix_installments_plan_id"), "installments", ["plan_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_installments_plan_id"), table_name="installments")
    op.drop_index(op.f("ix_installments_cutoff_date"), table_name="installments")
    op.drop_table("installments")
    op.drop_index(op.f("ix_installment_plans_account_id"), table_name="installment_plans")
    op.drop_table("installment_plans")
    # Dropped last: installment_plans depended on it
    op.drop_constraint(op.f("uq_movements_id_user_id"), "movements", type_="unique")
