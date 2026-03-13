"""Tests for MinerSelector — selection by incentive, filtering, edge cases."""

from unittest.mock import MagicMock

import numpy as np
import pytest

from gateway.core.exceptions import SubnetUnavailableError
from gateway.routing.metagraph_sync import MetagraphManager, SubnetMetagraphState
from gateway.routing.selector import MinerSelector


def _make_manager(metagraph: MagicMock | None) -> MagicMock:
    """Create a mock MetagraphManager that returns the given metagraph via get_state."""
    mgr = MagicMock(spec=MetagraphManager)
    if metagraph is None:
        mgr.get_state.return_value = None
    else:
        state = SubnetMetagraphState(netuid=1, metagraph=metagraph, sync_generation=1)
        mgr.get_state.return_value = state
    return mgr


@pytest.fixture
def mock_metagraph() -> MagicMock:
    """Metagraph with 3 miners: UID 0 highest incentive, UID 1 zero, UID 2 lower."""
    metagraph = MagicMock()
    metagraph.n = 3
    metagraph.incentive = np.array([0.5, 0.0, 0.3])
    metagraph.stake = np.array([100.0, 0.0, 50.0])
    metagraph.axons = [
        MagicMock(ip="1.2.3.4", port=8091),
        MagicMock(ip="", port=0),
        MagicMock(ip="5.6.7.8", port=8091),
    ]
    return metagraph


@pytest.fixture
def manager_with_metagraph(mock_metagraph: MagicMock) -> MetagraphManager:
    return _make_manager(mock_metagraph)


class TestMinerSelector:
    def test_selects_highest_incentive_miner(
        self, manager_with_metagraph: MetagraphManager, mock_metagraph: MagicMock
    ) -> None:
        selector = MinerSelector(manager_with_metagraph)
        axon = selector.select_miner(1)
        # UID 0 has highest incentive (0.5)
        assert axon is mock_metagraph.axons[0]

    def test_excludes_zero_incentive_miners(
        self, manager_with_metagraph: MetagraphManager
    ) -> None:
        selector = MinerSelector(manager_with_metagraph)
        axon = selector.select_miner(1)
        # UID 1 has zero incentive — should not be selected even if there
        assert axon.ip != ""

    def test_excludes_miners_without_axon(self) -> None:
        metagraph = MagicMock()
        metagraph.n = 2
        metagraph.incentive = np.array([0.5, 0.3])
        metagraph.stake = np.array([100.0, 50.0])
        metagraph.axons = [
            MagicMock(ip="", port=0),  # no reachable axon
            MagicMock(ip="", port=0),
        ]
        selector = MinerSelector(_make_manager(metagraph))
        with pytest.raises(SubnetUnavailableError):
            selector.select_miner(1)

    def test_raises_when_no_metagraph(self) -> None:
        selector = MinerSelector(_make_manager(None))
        with pytest.raises(SubnetUnavailableError) as exc_info:
            selector.select_miner(1)
        assert exc_info.value.reason == "no_metagraph"

    def test_raises_when_all_miners_zero_incentive(self) -> None:
        metagraph = MagicMock()
        metagraph.n = 2
        metagraph.incentive = np.array([0.0, 0.0])
        metagraph.stake = np.array([100.0, 50.0])
        metagraph.axons = [
            MagicMock(ip="1.2.3.4", port=8091),
            MagicMock(ip="5.6.7.8", port=8091),
        ]
        selector = MinerSelector(_make_manager(metagraph))
        with pytest.raises(SubnetUnavailableError) as exc_info:
            selector.select_miner(1)
        assert exc_info.value.reason == "no_eligible_miners"

    def test_excludes_zero_stake_miners(self) -> None:
        metagraph = MagicMock()
        metagraph.n = 2
        metagraph.incentive = np.array([0.9, 0.5])
        metagraph.stake = np.array([0.0, 100.0])
        metagraph.axons = [
            MagicMock(ip="1.2.3.4", port=8091),
            MagicMock(ip="5.6.7.8", port=8091),
        ]
        selector = MinerSelector(_make_manager(metagraph))
        axon = selector.select_miner(1)
        # UID 0 has zero stake — excluded despite highest incentive
        assert axon is metagraph.axons[1]

    def test_selects_second_best_when_top_offline(self) -> None:
        metagraph = MagicMock()
        metagraph.n = 3
        metagraph.incentive = np.array([0.9, 0.5, 0.3])
        metagraph.stake = np.array([100.0, 50.0, 30.0])
        metagraph.axons = [
            MagicMock(ip="", port=0),  # top miner offline
            MagicMock(ip="2.3.4.5", port=8091),
            MagicMock(ip="5.6.7.8", port=8091),
        ]
        selector = MinerSelector(_make_manager(metagraph))
        axon = selector.select_miner(1)
        assert axon is metagraph.axons[1]

    def test_port_zero_excluded(self) -> None:
        metagraph = MagicMock()
        metagraph.n = 2
        metagraph.incentive = np.array([0.9, 0.5])
        metagraph.stake = np.array([100.0, 50.0])
        metagraph.axons = [
            MagicMock(ip="1.2.3.4", port=0),  # port 0
            MagicMock(ip="5.6.7.8", port=8091),
        ]
        selector = MinerSelector(_make_manager(metagraph))
        axon = selector.select_miner(1)
        assert axon is metagraph.axons[1]

    def test_cache_invalidated_on_new_generation(self) -> None:
        """Cache should miss when sync_generation changes."""
        metagraph = MagicMock()
        metagraph.n = 2
        metagraph.incentive = np.array([0.5, 0.3])
        metagraph.stake = np.array([100.0, 50.0])
        metagraph.axons = [
            MagicMock(ip="1.2.3.4", port=8091),
            MagicMock(ip="5.6.7.8", port=8091),
        ]
        state = SubnetMetagraphState(netuid=1, metagraph=metagraph, sync_generation=1)
        mgr = MagicMock(spec=MetagraphManager)
        mgr.get_state.return_value = state

        selector = MinerSelector(mgr)
        axon1 = selector.select_miner(1)
        assert axon1 is metagraph.axons[0]

        # Simulate a new sync — new metagraph with different ranking
        new_metagraph = MagicMock()
        new_metagraph.n = 2
        new_metagraph.incentive = np.array([0.1, 0.9])
        new_metagraph.stake = np.array([50.0, 100.0])
        new_metagraph.axons = [
            MagicMock(ip="1.2.3.4", port=8091),
            MagicMock(ip="5.6.7.8", port=8091),
        ]
        state.metagraph = new_metagraph
        state.sync_generation = 2

        axon2 = selector.select_miner(1)
        assert axon2 is new_metagraph.axons[1]
