import random

import bittensor as bt
import structlog

from gateway.core.exceptions import SubnetUnavailableError
from gateway.routing.metagraph_sync import MetagraphManager, SubnetMetagraphState

logger = structlog.get_logger()


class MinerSelector:
    """Selects the best miner for a given subnet based on metagraph incentive scores.

    Caches the sorted eligible list per subnet, invalidated when the metagraph
    object changes (new sync replaces the reference).
    """

    def __init__(self, metagraph_manager: MetagraphManager) -> None:
        self._metagraph_manager = metagraph_manager
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

        weights = [e[1] for e in eligible]
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
