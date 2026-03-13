import bittensor as bt
import structlog

from gateway.core.config import settings

logger = structlog.get_logger()


def create_wallet() -> bt.Wallet:
    """Load wallet from configured path. Coldkey must be encrypted at rest."""
    wallet = bt.Wallet(
        name=settings.wallet_name,
        path=settings.wallet_path,
        hotkey=settings.hotkey_name,
    )
    logger.info("wallet_loaded", wallet_name=settings.wallet_name)
    return wallet


def create_subtensor() -> bt.Subtensor:
    """Connect to Bittensor network."""
    subtensor = bt.Subtensor(network=settings.subtensor_network)
    logger.info("subtensor_connected", network=settings.subtensor_network)
    return subtensor


def create_dendrite(wallet: bt.Wallet) -> bt.Dendrite:
    """Create Dendrite client for querying miners."""
    dendrite = bt.Dendrite(wallet=wallet)
    logger.info("dendrite_initialized")
    return dendrite
