import asyncio
import contextlib
import time
from dataclasses import dataclass

import bittensor as bt
import structlog

logger = structlog.get_logger()


_DEFAULT_STALENESS_SECONDS = 300  # 5 minutes


@dataclass
class SubnetMetagraphState:
    """Per-subnet metagraph state with sync tracking."""

    netuid: int
    metagraph: bt.Metagraph | None = None
    last_sync_time: float = 0.0
    last_sync_error: str | None = None
    consecutive_failures: int = 0
    staleness_threshold: float = _DEFAULT_STALENESS_SECONDS

    @property
    def is_stale(self) -> bool:
        """Metagraph is stale if exceeded staleness threshold since last successful sync."""
        if self.metagraph is None:
            return True
        return (time.time() - self.last_sync_time) > self.staleness_threshold


class MetagraphManager:
    """Manages metagraph state for all registered subnets."""

    def __init__(self, subtensor: bt.Subtensor, sync_interval: int = 120) -> None:
        self._subtensor = subtensor
        self._sync_interval = sync_interval
        self._subnets: dict[int, SubnetMetagraphState] = {}
        self._sync_task: asyncio.Task[None] | None = None

    def register_subnet(self, netuid: int) -> None:
        self._subnets[netuid] = SubnetMetagraphState(netuid=netuid)

    def get_metagraph(self, netuid: int) -> bt.Metagraph | None:
        state = self._subnets.get(netuid)
        return state.metagraph if state else None

    def get_state(self, netuid: int) -> SubnetMetagraphState | None:
        return self._subnets.get(netuid)

    def get_all_states(self) -> dict[int, SubnetMetagraphState]:
        """Return all registered subnet states (read-only view for health reporting)."""
        return dict(self._subnets)

    async def sync_all(self) -> None:
        """Sync all registered subnet metagraphs."""
        for netuid, state in self._subnets.items():
            try:
                loop = asyncio.get_running_loop()
                metagraph = await loop.run_in_executor(
                    None, self._subtensor.metagraph, netuid
                )
                state.metagraph = metagraph
                state.last_sync_time = time.time()
                state.last_sync_error = None
                state.consecutive_failures = 0
                logger.info(
                    "metagraph_synced",
                    netuid=netuid,
                    neurons=int(metagraph.n),
                )
            except Exception as exc:
                state.consecutive_failures += 1
                state.last_sync_error = str(exc)
                logger.warning(
                    "metagraph_sync_failed",
                    netuid=netuid,
                    error=str(exc),
                    consecutive_failures=state.consecutive_failures,
                )

    async def start_sync_loop(self) -> None:
        """Start background sync loop. Call as asyncio.create_task()."""
        await self.sync_all()
        while True:
            await asyncio.sleep(self._sync_interval)
            await self.sync_all()

    def start(self) -> None:
        """Create background task for sync loop."""
        self._sync_task = asyncio.create_task(self.start_sync_loop())

    async def stop(self) -> None:
        """Cancel sync task on shutdown."""
        if self._sync_task:
            self._sync_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._sync_task
