import bittensor as bt
import structlog

from gateway.core.exceptions import SubnetUnavailableError
from gateway.routing.metagraph_sync import MetagraphManager

logger = structlog.get_logger()


class MinerSelector:
    """Selects the best miner for a given subnet based on metagraph incentive scores."""

    def __init__(self, metagraph_manager: MetagraphManager) -> None:
        self._metagraph_manager = metagraph_manager

    def select_miner(self, netuid: int) -> bt.AxonInfo:
        """Select the top miner by incentive score, excluding ineligible miners.

        Raises SubnetUnavailableError if no eligible miners are found.

        Note: This is synchronous and runs on the event loop. The iteration
        over ~1024 neurons is fast enough for MVP (50 concurrent requests).
        Phase 2 should cache the sorted eligible list, invalidated on sync.
        """
        metagraph = self._metagraph_manager.get_metagraph(netuid)
        if metagraph is None:
            raise SubnetUnavailableError(f"sn{netuid}: no metagraph")

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

        if not eligible:
            raise SubnetUnavailableError(f"sn{netuid}: no eligible miners")

        eligible.sort(key=lambda x: x[1], reverse=True)
        best_uid, best_incentive, best_axon = eligible[0]

        logger.info(
            "miner_selected",
            netuid=netuid,
            miner_uid=best_uid,
            incentive=round(best_incentive, 6),
            eligible_count=len(eligible),
        )
        return best_axon
