"""phase9_sync_identity

Multi-device sync foundations. Entity tables get a `uuid` (globally unique
identity — integer PKs are device-local and collide across devices) and
`updated_at` (last-write-wins merge). Date-keyed health tables and the
settings singleton get `updated_at` only: they merge on `date`/id=1.

Existing rows are backfilled: fresh uuid4 each, updated_at = migration time.

Revision ID: c2d4e6f8a0b1
Revises: a1c9f0b3e264
Create Date: 2026-07-10 22:30:00.000000

"""
from datetime import datetime
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2d4e6f8a0b1'
down_revision: Union[str, None] = 'a1c9f0b3e264'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# uuid + updated_at (entity tables, sync by uuid)
UUID_TABLES = [
    'exercise', 'routine', 'routine_exercise', 'session',
    'session_exercise', 'set', 'plan_item', 'tracker', 'tracker_log',
]
# updated_at only (merge by date / singleton id)
TS_TABLES = ['weight_log', 'steps_log', 'sleep_log', 'nutrition_day', 'settings']


def upgrade() -> None:
    conn = op.get_bind()
    now = datetime.utcnow()

    for table in UUID_TABLES + TS_TABLES:
        op.add_column(table, sa.Column('updated_at', sa.DateTime(), nullable=True))
        conn.execute(
            sa.text(f'UPDATE "{table}" SET updated_at = :now'), {"now": now}
        )

    for table in UUID_TABLES:
        op.add_column(table, sa.Column('uuid', sa.String(length=36), nullable=True))
        ids = conn.execute(sa.text(f'SELECT id FROM "{table}"')).scalars().all()
        for row_id in ids:
            conn.execute(
                sa.text(f'UPDATE "{table}" SET uuid = :u WHERE id = :i'),
                {"u": str(uuid4()), "i": row_id},
            )
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.create_index(batch_op.f(f'ix_{table}_uuid'), ['uuid'], unique=True)


def downgrade() -> None:
    for table in UUID_TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_index(batch_op.f(f'ix_{table}_uuid'))
            batch_op.drop_column('uuid')
    for table in UUID_TABLES + TS_TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column('updated_at')
