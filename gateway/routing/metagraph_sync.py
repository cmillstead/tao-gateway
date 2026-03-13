import asyncio
import contextlib
import copy
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import bittensor as bt
import structlog

logger = structlog.get_logger()


_DEFAULT_STALENESS_SECONDS = 300  # 5 minutes
_ESCALATION_THRESHOLD = 5  # consecutive failures before logging at error level


@dataclass
class SubnetMetagraphState:
    """Per-subnet metagraph state with sync tracking."""

    netuid: int
    metagraph: bt.Metagraph | None = None
    last_sync_time: float = 0.0
    last_sync_error: str | None = None
    consecutive_failures: int = 0
    staleness_threshold: float = _DEFAULT_STALENESS_SECONDS
    sync_generation: int = 0

    @property
    def is_stale(self) -> bool:
        """Metagraph is stale if exceeded staleness threshold since last successful sync."""
        if self.metagraph is None:
            return True
        return (time.time() - self.last_sync_time) > self.staleness_threshold


class MetagraphManager:
    """Manages metagraph state for all registered subnets."""

    def __init__(
        self,
        subtensor: bt.Subtensor,
        sync_interval: int = 120,
        sync_timeout: float = 30.0,
    ) -> None:
        self._subtensor = subtensor
        self._sync_interval = sync_interval
        self._sync_timeout = sync_timeout
        self._subnets: dict[int, SubnetMetagraphState] = {}
        self._sync_task: asyncio.Task[None] | None = None
        self._executor = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="metagraph-sync"
        )

    def register_subnet(self, netuid: int) -> None:
        self._subnets[netuid] = SubnetMetagraphState(netuid=netuid)

    def get_metagraph(self, netuid: int) -> bt.Metagraph | None:
        state = self._subnets.get(netuid)
        return state.metagraph if state else None

    def get_state(self, netuid: int) -> SubnetMetagraphState | None:
        return self._subnets.get(netuid)

    def get_all_states(self) -> dict[int, SubnetMetagraphState]:
        """Return shallow copies of all subnet states for health reporting.

        Callers get independent copies — mutations do not affect the manager.
        The metagraph reference is shared (read-only by convention) to avoid
        expensive deep copies.
        """
        return {netuid: copy.copy(state) for netuid, state in self._subnets.items()}

    async def sync_all(self) -> None:
        """Sync all registered subnet metagraphs."""
        for netuid, state in self._subnets.items():
            try:
                loop = asyncio.get_running_loop()
                metagraph = await asyncio.wait_for(
                    loop.run_in_executor(
                        self._executor, self._subtensor.metagraph, netuid
                    ),
                    timeout=self._sync_timeout,
                )
                state.metagraph = metagraph
                state.last_sync_time = time.time()
                state.last_sync_error = None
                state.consecutive_failures = 0
                state.sync_generation += 1
                logger.info(
                    "metagraph_synced",
                    netuid=netuid,
                    neurons=int(metagraph.n),
                )
            except Exception as exc:
                state.consecutive_failures += 1
                state.last_sync_error = str(exc)
                log = (
                    logger.error
                    if state.consecutive_failures >= _ESCALATION_THRESHOLD
                    else logger.warning
                )
                log(
                    "metagraph_sync_failed",
                    netuid=netuid,
                    error=str(exc),
                    consecutive_failures=state.consecutive_failures,
                )

    async def _sync_loop(self) -> None:
        """Background loop that syncs periodically. Does NOT run initial sync."""
        while True:
            await asyncio.sleep(self._sync_interval)
            await self.sync_all()

    async def start(self) -> None:
        """Run initial sync (awaited, so failures are visible) then start background loop."""
        await self.sync_all()
        self._sync_task = asyncio.create_task(self._sync_loop())

    async def stop(self) -> None:
        """Cancel sync task and shut down executor on shutdown."""
        if self._sync_task:
            self._sync_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._sync_task
        self._executor.shutdown(wait=False, cancel_futures=True)
