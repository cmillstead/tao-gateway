"""add updated_at triggers for organizations and api_keys

Revision ID: 1f760edb6b6a
Revises: 6873921e4697
Create Date: 2026-03-12

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1f760edb6b6a"
down_revision: Union[str, Sequence[str], None] = "6873921e4697"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Postgres trigger function that sets updated_at = now() on row update.
# Shared by both tables.
_CREATE_FUNCTION = """
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

_DROP_FUNCTION = "DROP FUNCTION IF EXISTS set_updated_at();"

_TABLES = ("organizations", "api_keys")


def upgrade() -> None:
    """Create shared trigger function and apply to both tables."""
    op.execute(_CREATE_FUNCTION)
    for table in _TABLES:
        op.execute(
            f"CREATE TRIGGER trg_{table}_updated_at "
            f"BEFORE UPDATE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
        )


def downgrade() -> None:
    """Remove triggers and function."""
    for table in _TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table};")
    op.execute(_DROP_FUNCTION)
