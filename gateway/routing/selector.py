import bittensor as bt
import structlog

from gateway.core.exceptions import SubnetUnavailableError
from gateway.routing.metagraph_sync import MetagraphManager

logger = structlog.get_logger()


class MinerSelector:
    """Selects the best miner for a given subnet based on metagraph incentive scores.

    Caches the sorted eligible list per subnet, invalidated when the metagraph
    object changes (new sync replaces the reference).
    """

    def __init__(self, metagraph_manager: MetagraphManager) -> None:
        self._metagraph_manager = metagraph_manager
        # Cache: netuid -> (metagraph_id, sorted_eligible_list)
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
        metagraph = self._metagraph_manager.get_metagraph(netuid)
        if metagraph is None:
            raise SubnetUnavailableError(f"sn{netuid}", reason="no_metagraph")

        # Use cached eligible list if metagraph hasn't changed
        cached = self._cache.get(netuid)
        if cached is not None and cached[0] == id(metagraph):
            eligible = cached[1]
        else:
            eligible = self._build_eligible(metagraph)
            self._cache[netuid] = (id(metagraph), eligible)

        if not eligible:
            raise SubnetUnavailableError(f"sn{netuid}", reason="no_eligible_miners")

        best_uid, best_incentive, best_axon = eligible[0]

        logger.info(
            "miner_selected",
            netuid=netuid,
            miner_uid=best_uid,
            incentive=round(best_incentive, 6),
            eligible_count=len(eligible),
        )
        return best_axon
