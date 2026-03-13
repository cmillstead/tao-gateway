"""Tests for MetagraphManager — sync success, failure, staleness, timing."""

import asyncio
import time
from unittest.mock import MagicMock

import numpy as np
import pytest

from gateway.routing.metagraph_sync import MetagraphManager, SubnetMetagraphState


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

    async def test_sync_failure_increments_consecutive(
        self, manager: MetagraphManager, mock_subtensor: MagicMock
    ) -> None:
        mock_subtensor.metagraph.side_effect = ConnectionError("down")
        await manager.sync_all()
        await manager.sync_all()
        state = manager.get_state(1)
        assert state is not None
        assert state.consecutive_failures == 2

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

    async def test_staleness_detection(
        self, manager: MetagraphManager, mock_subtensor: MagicMock
    ) -> None:
        await manager.sync_all()
        state = manager.get_state(1)
        assert state is not None
        # Artificially age the sync time
        state.last_sync_time = time.time() - 400  # >5min
        assert state.is_stale is True

    async def test_start_and_stop(
        self, manager: MetagraphManager, mock_subtensor: MagicMock
    ) -> None:
        manager._sync_interval = 0.01  # fast for test
        manager.start()
        await asyncio.sleep(0.05)
        await manager.stop()
        # Should have synced at least once
        state = manager.get_state(1)
        assert state is not None
        assert state.metagraph is not None
