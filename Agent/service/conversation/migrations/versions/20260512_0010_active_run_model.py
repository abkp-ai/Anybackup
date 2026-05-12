from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260512_0010"
down_revision = "20260426_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("t_conversation") as batch_op:
        batch_op.add_column(sa.Column("f_active_run_id", sa.String(length=128), nullable=True))
        batch_op.drop_column("f_active_turn_id")
        batch_op.drop_column("f_interaction_status")


def downgrade() -> None:
    with op.batch_alter_table("t_conversation") as batch_op:
        batch_op.add_column(sa.Column("f_interaction_status", sa.String(length=32), nullable=False))
        batch_op.add_column(sa.Column("f_active_turn_id", sa.BigInteger(), nullable=True))
        batch_op.drop_column("f_active_run_id")
