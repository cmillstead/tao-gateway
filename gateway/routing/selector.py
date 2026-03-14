import ipaddress
import random
from typing import TYPE_CHECKING

import bittensor as bt
import structlog

from gateway.core.exceptions import SubnetUnavailableError
from gateway.routing.metagraph_sync import MetagraphManager, SubnetMetagraphState

if TYPE_CHECKING:
    from gateway.routing.scorer import MinerScorer

logger = structlog.get_logger()


def _is_safe_ip(ip_str: str) -> bool:
    """Return False for private, loopback, link-local, and reserved IPs."""
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return addr.is_global


class MinerSelector:
    """Selects the best miner for a given subnet based on metagraph incentive scores.

    Caches the sorted eligible list per subnet, invalidated when the metagraph
    object changes (new sync replaces the reference).
    """

    def __init__(
        self,
        metagraph_manager: MetagraphManager,
        scorer: "MinerScorer | None" = None,
        quality_weight: float = 0.3,
    ) -> None:
        self._metagraph_manager = metagraph_manager
        self._scorer = scorer
        self._quality_weight = quality_weight
        # Cache: netuid -> (sync_generation, sorted_eligible_list)
        self._cache: dict[int, tuple[int, list[tuple[int, float, bt.AxonInfo]]]] = {}

    def _build_eligible(
        self, metagraph: bt.Metagraph
    ) -> list[tuple[int, float, bt.AxonInfo]]:
        eligible: list[tuple[int, float, bt.AxonInfo]] = []
        for uid in range(int(metagraph.n)):
            incentive = float(metagraph.incentive[uid])
            stake = float(metagraph.stake[uid])
            axon = metagraph.axons[uid]

            if incentive <= 0:
                continue
            if stake <= 0:
                continue
            if not axon.ip or axon.port == 0:
                continue
            if not _is_safe_ip(axon.ip):
                logger.warning(
                    "miner_unsafe_ip_skipped",
                    uid=uid,
                    ip=axon.ip,
                )
                continue

            eligible.append((uid, incentive, axon))

        eligible.sort(key=lambda x: x[1], reverse=True)
        return eligible

    def select_miner(self, netuid: int) -> bt.AxonInfo:
        """Select the top miner by incentive score, excluding ineligible miners.

        Raises SubnetUnavailableError if no eligible miners are found.
        """
        state: SubnetMetagraphState | None = self._metagraph_manager.get_state(netuid)
        if state is None or state.metagraph is None:
            raise SubnetUnavailableError(f"sn{netuid}", reason="no_metagraph")

        metagraph = state.metagraph

        # Use cached eligible list if metagraph hasn't been re-synced.
        # sync_generation is a monotonic counter — immune to id() reuse after GC.
        cached = self._cache.get(netuid)
        if cached is not None and cached[0] == state.sync_generation:
            eligible = cached[1]
        else:
            eligible = self._build_eligible(metagraph)
            self._cache[netuid] = (state.sync_generation, eligible)

        if not eligible:
            raise SubnetUnavailableError(f"sn{netuid}", reason="no_eligible_miners")

        # Blend incentive with quality scores if scorer is available
        quality_scores: dict[str, float] = {}
        if self._scorer is not None and self._quality_weight > 0:
            quality_scores = self._scorer.get_scores(netuid)

        weights: list[float] = []
        for _uid, incentive, axon_info in eligible:
            q_score = quality_scores.get(axon_info.hotkey)
            if q_score is not None and self._quality_weight > 0:
                blended = incentive * (1 - self._quality_weight) + q_score * self._quality_weight
            else:
                blended = incentive
            weights.append(max(blended, 1e-9))  # Avoid zero weights

        (selected,) = random.choices(eligible, weights=weights, k=1)
        sel_uid, sel_incentive, sel_axon = selected

        logger.info(
            "miner_selected",
            netuid=netuid,
            miner_uid=sel_uid,
            incentive=round(sel_incentive, 6),
            eligible_count=len(eligible),
        )
        return sel_axon
