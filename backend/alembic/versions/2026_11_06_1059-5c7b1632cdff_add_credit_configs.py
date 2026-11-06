"""Add credit_configs: limit, cutoff day and payment due rule of each credit account.

Revision ID: 5c7b1632cdff
Revises: 07f9aebe6cdc
Create Date: 2026-11-06 10:59:23.586938

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5c7b1632cdff"
down_revision: str | Sequence[str] | None = "07f9aebe6cdc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "credit_configs",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("credit_limit", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("cutoff_day", sa.SmallInteger(), nullable=False),
        sa.Column(
            "payment_due_rule",
            sa.Enum(
                "fixed_day",
                "days_after_cutoff",
                name="payment_due_rule",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("payment_due_value", sa.SmallInteger(), nullable=False),
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
            "(payment_due_rule = 'fixed_day' AND payment_due_value BETWEEN 1 AND 31)"
            " OR (payment_due_rule = 'days_after_cutoff' AND payment_due_value BETWEEN 1 AND 60)",
            name=op.f("ck_credit_configs_payment_due_value_in_range"),
        ),
        sa.CheckConstraint(
            "credit_limit > 0", name=op.f("ck_credit_configs_credit_limit_positive")
        ),
        sa.CheckConstraint(
            "cutoff_day BETWEEN 1 AND 31", name=op.f("ck_credit_configs_cutoff_day_in_range")
        ),
        sa.ForeignKeyConstraint(
            ["account_id", "user_id"],
            ["accounts.id", "accounts.user_id"],
            name=op.f("fk_credit_configs_account_id_user_id_accounts"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_credit_configs_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_credit_configs")),
        sa.UniqueConstraint("account_id", name=op.f("uq_credit_configs_account_id")),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("credit_configs")
