"""add is_active server default

Revision ID: a1b2c3d4e5f6
Revises: 795f9c954fcb
Create Date: 2026-03-12 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '795f9c954fcb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add server_default to api_keys.is_active column."""
    op.alter_column(
        'api_keys',
        'is_active',
        server_default=sa.text('true'),
    )


def downgrade() -> None:
    """Remove server_default from api_keys.is_active column."""
    op.alter_column(
        'api_keys',
        'is_active',
        server_default=None,
    )
