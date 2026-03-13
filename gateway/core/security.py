from typing import TYPE_CHECKING, Any

from argon2 import PasswordHasher

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# Shared hasher instance — all modules must import from here so argon2
# parameters stay consistent across auth, API key generation, and validation.
# Parameters are pinned explicitly to prevent silent changes on library upgrades.
ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)


async def try_rehash(
    db: "AsyncSession",
    record: Any,
    hash_attr: str,
    plaintext: str,
) -> None:
    """Best-effort argon2 rehash — don't fail the caller if this errors."""
    try:
        current_hash = getattr(record, hash_attr)
        if ph.check_needs_rehash(current_hash):
            setattr(record, hash_attr, ph.hash(plaintext))
            await db.commit()
    except Exception:
        import structlog
        structlog.get_logger().warning("rehash_failed", record_type=type(record).__name__)
        await db.rollback()
