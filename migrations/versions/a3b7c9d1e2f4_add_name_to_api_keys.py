"""add name column to api_keys

Revision ID: a3b7c9d1e2f4
Revises: f8828ff1eb3b
Create Date: 2026-03-14 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3b7c9d1e2f4'
down_revision: Union[str, Sequence[str], None] = 'f8828ff1eb3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('api_keys', sa.Column('name', sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column('api_keys', 'name')
