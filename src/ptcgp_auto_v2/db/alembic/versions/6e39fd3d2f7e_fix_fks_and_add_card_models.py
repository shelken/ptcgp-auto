"""Fix FKs and Add Card Models

Revision ID: 6e39fd3d2f7e
Revises: 331afd912809
Create Date: 2026-01-23 13:33:51.342301

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "6e39fd3d2f7e"
down_revision: Union[str, Sequence[str], None] = "331afd912809"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Create CardSet table
    op.create_table(
        "card_sets",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("code", sqlmodel.AutoString(), nullable=False),
        sa.Column("name", sqlmodel.AutoString(), nullable=False),
        sa.Column("release_date", sqlmodel.AutoString(), nullable=True),
        sa.Column("total_cards", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("code"),
    )

    # 2. Create Card table
    op.create_table(
        "cards",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("set_code", sqlmodel.AutoString(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.AutoString(), nullable=False),
        sa.Column("rarity", sqlmodel.AutoString(), nullable=False),
        sa.Column("image_url", sqlmodel.AutoString(), nullable=False),
        sa.Column("local_image_path", sqlmodel.AutoString(), nullable=True),
        sa.Column("data", sqlmodel.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(
            ["set_code"],
            ["card_sets.code"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cards_set_code"), "cards", ["set_code"], unique=False)

    # 3. Create CardPack table
    op.create_table(
        "card_packs",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("card_id", sa.Integer(), nullable=False),
        sa.Column("pack_name", sqlmodel.AutoString(), nullable=False),
        sa.ForeignKeyConstraint(
            ["card_id"],
            ["cards.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_card_packs_card_id"), "card_packs", ["card_id"], unique=False
    )

    # 4. Attempt to fix broken FKs (Explicitly recreating tables with correct FKs)
    # Using batch_alter_table to rebuild 'account_pack_config'
    with op.batch_alter_table("account_pack_config", schema=None) as batch_op:
        # We define the correct FK to 'accounts'
        batch_op.create_foreign_key(
            "fk_account_pack_config_accounts",
            "accounts",
            ["account_id"],
            ["id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("pack_records", schema=None) as batch_op:
        batch_op.create_foreign_key(
            "fk_pack_records_accounts",
            "accounts",
            ["account_id"],
            ["id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("task_instances", schema=None) as batch_op:
        batch_op.create_foreign_key(
            "fk_task_instances_accounts",
            "accounts",
            ["account_id"],
            ["id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("accounts", schema=None) as batch_op:
        batch_op.create_foreign_key(
            "fk_accounts_task_plans",
            "task_plans",
            ["task_plan_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # 5. Drop temporary tables if they exist (ignore errors if they don't)
    try:
        op.drop_table("accounts_old")
    except Exception:
        pass

    try:
        op.drop_table("task_plans_old")
    except Exception:
        pass


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_card_packs_card_id"), table_name="card_packs")
    op.drop_table("card_packs")
    op.drop_index(op.f("ix_cards_set_code"), table_name="cards")
    op.drop_table("cards")
    op.drop_table("card_sets")
