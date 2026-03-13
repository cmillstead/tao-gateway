"""add is_active server default and updated_at columns

Revision ID: 6873921e4697
Revises: 795f9c954fcb
Create Date: 2026-03-12 23:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6873921e4697"
down_revision: Union[str, Sequence[str], None] = "795f9c954fcb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add server_default to is_active and updated_at to both tables."""
    # Fix: is_active should have a server_default
    op.alter_column(
        "api_keys",
        "is_active",
        server_default=sa.text("true"),
    )

    # Add updated_at to organizations
    op.add_column(
        "organizations",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Add updated_at to api_keys
    op.add_column(
        "api_keys",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Remove updated_at columns and is_active server_default."""
    op.drop_column("api_keys", "updated_at")
    op.drop_column("organizations", "updated_at")
    op.alter_column(
        "api_keys",
        "is_active",
        server_default=None,
    )
