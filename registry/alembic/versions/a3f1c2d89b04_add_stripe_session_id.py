"""add stripe_session_id to cbt_transactions

Revision ID: a3f1c2d89b04
Revises: 1da8d3d765ce
Create Date: 2026-03-24

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a3f1c2d89b04'
down_revision: Union[str, Sequence[str], None] = '1da8d3d765ce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('cbt_transactions', sa.Column('stripe_session_id', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('cbt_transactions', 'stripe_session_id')
