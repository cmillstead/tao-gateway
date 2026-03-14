from sqlalchemy import Float, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from gateway.models.base import Base, TimestampMixin


class MinerScore(TimestampMixin, Base):
    __tablename__ = "miner_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    miner_uid: Mapped[int] = mapped_column(Integer, nullable=False)
    hotkey: Mapped[str] = mapped_column(String(64), nullable=False)
    netuid: Mapped[int] = mapped_column(Integer, nullable=False)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    __table_args__ = (
        UniqueConstraint("hotkey", "netuid", name="uq_miner_scores_hotkey_netuid"),
        Index("ix_miner_scores_netuid_quality_score", "netuid", "quality_score"),
    )
