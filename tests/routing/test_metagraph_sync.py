"""Tests for MetagraphManager — sync success, failure, staleness, timing."""

import asyncio
import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from gateway.routing.metagraph_sync import MetagraphManager, SubnetMetagraphState, logger


@pytest.fixture
def mock_subtensor() -> MagicMock:
    subtensor = MagicMock()
    metagraph = MagicMock()
    metagraph.n = 3
    metagraph.incentive = np.array([0.5, 0.0, 0.3])
    metagraph.stake = np.array([100.0, 0.0, 50.0])
    metagraph.axons = [
        MagicMock(ip="1.2.3.4", port=8091),
        MagicMock(ip="", port=0),
        MagicMock(ip="5.6.7.8", port=8091),
    ]
    subtensor.metagraph.return_value = metagraph
    return subtensor


@pytest.fixture
def manager(mock_subtensor: MagicMock) -> MetagraphManager:
    mgr = MetagraphManager(subtensor=mock_subtensor, sync_interval=120)
    mgr.register_subnet(1)
    return mgr


class TestSubnetMetagraphState:
    def test_is_stale_when_no_metagraph(self) -> None:
        state = SubnetMetagraphState(netuid=1)
        assert state.is_stale is True

    def test_is_stale_when_old_sync(self) -> None:
        state = SubnetMetagraphState(netuid=1, metagraph=MagicMock(), last_sync_time=0.0)
        assert state.is_stale is True

    def test_not_stale_when_recent_sync(self) -> None:
        state = SubnetMetagraphState(
            netuid=1, metagraph=MagicMock(), last_sync_time=time.time()
        )
        assert state.is_stale is False


class TestMetagraphManager:
    def test_register_subnet(self, manager: MetagraphManager) -> None:
        state = manager.get_state(1)
        assert state is not None
        assert state.netuid == 1

    def test_get_metagraph_before_sync(self, manager: MetagraphManager) -> None:
        assert manager.get_metagraph(1) is None

    def test_get_metagraph_unknown_subnet(self, manager: MetagraphManager) -> None:
        assert manager.get_metagraph(999) is None

    @pytest.mark.asyncio
    async def test_sync_all_success(
        self, manager: MetagraphManager, mock_subtensor: MagicMock
    ) -> None:
        await manager.sync_all()
        state = manager.get_state(1)
        assert state is not None
        assert state.metagraph is not None
        assert state.last_sync_error is None
        assert state.consecutive_failures == 0
        assert state.is_stale is False

    @pytest.mark.asyncio
    async def test_sync_all_failure_keeps_cached(
        self, manager: MetagraphManager, mock_subtensor: MagicMock
    ) -> None:
        # First sync succeeds
        await manager.sync_all()
        state = manager.get_state(1)
        assert state is not None
        first_metagraph = state.metagraph

        # Second sync fails
        mock_subtensor.metagraph.side_effect = ConnectionError("network down")
        await manager.sync_all()
        assert state.metagraph is first_metagraph  # cached metagraph preserved
        assert state.last_sync_error is not None
        assert state.consecutive_failures == 1

    @pytest.mark.asyncio
    async def test_sync_failure_increments_consecutive(
        self, manager: MetagraphManager, mock_subtensor: MagicMock
    ) -> None:
        mock_subtensor.metagraph.side_effect = ConnectionError("down")
        await manager.sync_all()
        await manager.sync_all()
        state = manager.get_state(1)
        assert state is not None
        assert state.consecutive_failures == 2

    @pytest.mark.asyncio
    async def test_sync_success_resets_failures(
        self, manager: MetagraphManager, mock_subtensor: MagicMock
    ) -> None:
        mock_subtensor.metagraph.side_effect = ConnectionError("down")
        await manager.sync_all()
        mock_subtensor.metagraph.side_effect = None
        mock_subtensor.metagraph.return_value = MagicMock(n=3)
        await manager.sync_all()
        state = manager.get_state(1)
        assert state is not None
        assert state.consecutive_failures == 0
        assert state.last_sync_error is None

    @pytest.mark.asyncio
    async def test_staleness_detection(
        self, manager: MetagraphManager, mock_subtensor: MagicMock
    ) -> None:
        await manager.sync_all()
        state = manager.get_state(1)
        assert state is not None
        # Artificially age the sync time
        state.last_sync_time = time.time() - 400  # >5min
        assert state.is_stale is True

    @pytest.mark.asyncio
    async def test_start_runs_initial_sync(
        self, manager: MetagraphManager, mock_subtensor: MagicMock
    ) -> None:
        await manager.start()
        state = manager.get_state(1)
        assert state is not None
        assert state.metagraph is not None
        assert state.consecutive_failures == 0
        await manager.stop()

    @pytest.mark.asyncio
    async def test_background_loop_syncs_periodically(
        self, mock_subtensor: MagicMock
    ) -> None:
        """Verify the background loop fires after the initial sync."""
        sync_count = 0
        original_metagraph = mock_subtensor.metagraph

        def counting_metagraph(netuid: int) -> MagicMock:
            nonlocal sync_count
            sync_count += 1
            return original_metagraph(netuid)

        mock_subtensor.metagraph = counting_metagraph

        mgr = MetagraphManager(subtensor=mock_subtensor, sync_interval=0.01)
        mgr.register_subnet(1)
        await mgr.start()  # initial sync = 1
        # Wait long enough for at least one background sync
        await asyncio.sleep(0.1)
        await mgr.stop()
        # Must have synced more than once (initial + at least one loop iteration)
        assert sync_count >= 2, f"Expected >=2 syncs, got {sync_count}"

    @pytest.mark.asyncio
    async def test_sync_timeout_treated_as_failure(
        self, mock_subtensor: MagicMock
    ) -> None:
        """A sync that exceeds sync_timeout is treated as a failure, not a hang."""

        def slow_metagraph(netuid: int) -> None:
            import time as _t

            _t.sleep(0.2)  # longer than timeout

        mock_subtensor.metagraph = slow_metagraph
        mgr = MetagraphManager(
            subtensor=mock_subtensor, sync_interval=120, sync_timeout=0.01
        )
        mgr.register_subnet(1)
        await mgr.sync_all()
        state = mgr.get_state(1)
        assert state is not None
        assert state.metagraph is None  # never got a result
        assert state.consecutive_failures == 1
        assert state.last_sync_error is not None

    @pytest.mark.asyncio
    async def test_escalation_after_repeated_failures(
        self, manager: MetagraphManager, mock_subtensor: MagicMock
    ) -> None:
        """Log level escalates from warning to error after threshold consecutive failures."""
        mock_subtensor.metagraph.side_effect = ConnectionError("down")

        warning_count = 0
        error_count = 0

        with patch.object(
            logger, "warning", wraps=logger.warning
        ) as mock_warn, patch.object(
            logger, "error", wraps=logger.error
        ) as mock_err:
            for _ in range(6):  # exceed _ESCALATION_THRESHOLD (5)
                await manager.sync_all()
            warning_count = mock_warn.call_count
            error_count = mock_err.call_count

        state = manager.get_state(1)
        assert state is not None
        assert state.consecutive_failures == 6
        # First 4 failures log warning, failures 5+ log error
        assert warning_count == 4, f"Expected 4 warnings, got {warning_count}"
        assert error_count == 2, f"Expected 2 errors, got {error_count}"
