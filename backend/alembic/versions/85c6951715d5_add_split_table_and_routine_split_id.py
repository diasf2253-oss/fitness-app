"""add split table and routine.split_id

Revision ID: 85c6951715d5
Revises: 503345d8e0d4
Create Date: 2026-09-08 16:26:00.224055

"""
from typing import Sequence, Union

import uuid
from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '85c6951715d5'
down_revision: Union[str, None] = '503345d8e0d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "split",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("uuid", sa.String(36), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_split_uuid", "split", ["uuid"], unique=True)
    op.create_index("ix_split_user_id", "split", ["user_id"])
    op.add_column("routine", sa.Column("split_id", sa.Integer(), nullable=True))
    op.create_index("ix_routine_split_id", "routine", ["split_id"])

    # Backfill: give every user who already has routines one split holding them,
    # so nothing is orphaned in the new two-level Routines page. Named
    # generically because we can't know what their existing days represent.
    conn = op.get_bind()
    now = datetime.utcnow()
    user_ids = [
        row[0] for row in conn.execute(
            sa.text("SELECT DISTINCT user_id FROM routine WHERE split_id IS NULL")
        )
    ]
    for user_id in user_ids:
        split_uuid = str(uuid.uuid4())
        conn.execute(
            sa.text(
                "INSERT INTO split (uuid, updated_at, user_id, name, position, created_at) "
                "VALUES (:uuid, :now, :user_id, :name, 0, :now)"
            ),
            {"uuid": split_uuid, "now": now, "user_id": user_id, "name": "My split"},
        )
        split_id = conn.execute(
            sa.text("SELECT id FROM split WHERE uuid = :uuid"), {"uuid": split_uuid}
        ).scalar()
        conn.execute(
            sa.text(
                "UPDATE routine SET split_id = :split_id "
                "WHERE user_id = :user_id AND split_id IS NULL"
            ),
            {"split_id": split_id, "user_id": user_id},
        )


def downgrade() -> None:
    with op.batch_alter_table("routine") as batch:
        batch.drop_column("split_id")
    op.drop_table("split")
