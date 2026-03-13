"""Tests for MinerSelector — selection by incentive, filtering, edge cases."""

from unittest.mock import MagicMock

import numpy as np
import pytest

from gateway.core.exceptions import SubnetUnavailableError
from gateway.routing.metagraph_sync import MetagraphManager
from gateway.routing.selector import MinerSelector


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
    mgr = MagicMock(spec=MetagraphManager)
    mgr.get_metagraph.return_value = mock_metagraph
    return mgr


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
        mgr = MagicMock(spec=MetagraphManager)
        mgr.get_metagraph.return_value = metagraph
        selector = MinerSelector(mgr)
        with pytest.raises(SubnetUnavailableError):
            selector.select_miner(1)

    def test_raises_when_no_metagraph(self) -> None:
        mgr = MagicMock(spec=MetagraphManager)
        mgr.get_metagraph.return_value = None
        selector = MinerSelector(mgr)
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
        mgr = MagicMock(spec=MetagraphManager)
        mgr.get_metagraph.return_value = metagraph
        selector = MinerSelector(mgr)
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
        mgr = MagicMock(spec=MetagraphManager)
        mgr.get_metagraph.return_value = metagraph
        selector = MinerSelector(mgr)
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
        mgr = MagicMock(spec=MetagraphManager)
        mgr.get_metagraph.return_value = metagraph
        selector = MinerSelector(mgr)
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
        mgr = MagicMock(spec=MetagraphManager)
        mgr.get_metagraph.return_value = metagraph
        selector = MinerSelector(mgr)
        axon = selector.select_miner(1)
        assert axon is metagraph.axons[1]
