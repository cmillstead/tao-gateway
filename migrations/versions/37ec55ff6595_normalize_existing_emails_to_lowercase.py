"""normalize existing emails to lowercase

Revision ID: 37ec55ff6595
Revises: 1f760edb6b6a
Create Date: 2026-03-13

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "37ec55ff6595"
down_revision: str | Sequence[str] | None = "1f760edb6b6a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Normalize all existing organization emails to lowercase/trimmed."""
    op.execute("UPDATE organizations SET email = LOWER(TRIM(email))")


def downgrade() -> None:
    """No-op: cannot restore original casing."""
    pass
