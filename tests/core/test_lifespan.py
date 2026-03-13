"""Tests for lifespan startup/shutdown behavior — Bittensor initialization paths."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestLifespanStartupFailure:
    """Test that lifespan aborts when initial metagraph sync yields no data."""

    @pytest.mark.asyncio
    async def test_startup_raises_when_initial_metagraph_empty(self) -> None:
        """If initial sync completes but metagraph is still None, startup must fail."""
        mock_subtensor = MagicMock()
        # metagraph() returns a metagraph with n=0 and None-like behavior
        # but we make sync_all succeed while leaving metagraph as None by
        # having the subtensor raise so sync_all catches and keeps None
        mock_subtensor.metagraph.side_effect = ConnectionError("chain unreachable")

        with (
            patch("gateway.main.create_wallet", return_value=MagicMock()),
            patch("gateway.main.create_subtensor", return_value=mock_subtensor),
            patch("gateway.main.create_dendrite", return_value=MagicMock()),
        ):
            from fastapi import FastAPI

            from gateway.main import lifespan

            test_app = FastAPI()
            with pytest.raises(RuntimeError, match="Initial metagraph sync failed"):
                async with lifespan(test_app):
                    pass

    @pytest.mark.asyncio
    async def test_startup_logs_error_details_on_bittensor_failure(self) -> None:
        """Bittensor init failure logs include the actual error details."""
        with (
            patch(
                "gateway.main.create_wallet",
                side_effect=FileNotFoundError("wallet not found at /fake/path"),
            ),
            patch("gateway.main.logger") as mock_logger,
        ):
            from fastapi import FastAPI

            from gateway.main import lifespan

            test_app = FastAPI()
            with pytest.raises(FileNotFoundError):
                async with lifespan(test_app):
                    pass

            mock_logger.error.assert_called_once()
            call_kwargs = mock_logger.error.call_args
            assert "error" in call_kwargs.kwargs or (
                len(call_kwargs.args) > 1 and "wallet not found" in str(call_kwargs)
            )


class TestLifespanBittensorDisabled:
    """Test that lifespan succeeds without Bittensor when disabled."""

    @pytest.mark.asyncio
    async def test_startup_succeeds_without_bittensor(self) -> None:
        """When enable_bittensor=False, gateway starts without wallet/subtensor."""
        with (
            patch("gateway.main.settings") as mock_settings,
            patch("gateway.main.get_engine") as mock_engine,
            patch("gateway.main.get_redis") as mock_redis,
            patch("gateway.main.close_redis", new_callable=AsyncMock),
        ):
            mock_settings.enable_bittensor = False
            mock_settings.app_version = "0.0.0-test"

            mock_conn = AsyncMock()
            mock_engine_instance = MagicMock()
            mock_engine_instance.connect.return_value.__aenter__ = AsyncMock(
                return_value=mock_conn
            )
            mock_engine_instance.connect.return_value.__aexit__ = AsyncMock()
            mock_engine_instance.dispose = AsyncMock()
            mock_engine.return_value = mock_engine_instance

            mock_redis_instance = AsyncMock()
            mock_redis.return_value = mock_redis_instance

            from fastapi import FastAPI

            from gateway.main import lifespan

            test_app = FastAPI()
            async with lifespan(test_app):
                assert not hasattr(test_app.state, "dendrite")
                assert not hasattr(test_app.state, "metagraph_manager")


class TestLifespanShutdown:
    """Test that shutdown cleans up Bittensor resources."""

    @pytest.mark.asyncio
    async def test_dendrite_session_closed_on_shutdown(self) -> None:
        """dendrite.aclose_session() is called during shutdown."""
        mock_subtensor = MagicMock()
        mock_metagraph = MagicMock()
        mock_metagraph.n = 0
        mock_subtensor.metagraph.return_value = mock_metagraph

        mock_dendrite = MagicMock()
        mock_dendrite.aclose_session = AsyncMock()

        with (
            patch("gateway.main.create_wallet", return_value=MagicMock()),
            patch("gateway.main.create_subtensor", return_value=mock_subtensor),
            patch("gateway.main.create_dendrite", return_value=mock_dendrite),
            patch("gateway.main.get_engine") as mock_engine,
            patch("gateway.main.get_redis") as mock_redis,
            patch("gateway.main.close_redis", new_callable=AsyncMock),
        ):
            # Mock DB and Redis to pass startup checks
            mock_conn = AsyncMock()
            mock_engine_instance = MagicMock()
            mock_engine_instance.connect.return_value.__aenter__ = AsyncMock(
                return_value=mock_conn
            )
            mock_engine_instance.connect.return_value.__aexit__ = AsyncMock()
            mock_engine_instance.dispose = AsyncMock()
            mock_engine.return_value = mock_engine_instance

            mock_redis_instance = AsyncMock()
            mock_redis.return_value = mock_redis_instance

            from fastapi import FastAPI

            from gateway.main import lifespan

            test_app = FastAPI()

            # metagraph sync returns n=0, but metagraph is not None so startup passes
            # However, the startup guard checks get_metagraph() which returns
            # the mock_metagraph (not None). So startup should proceed.
            async with lifespan(test_app):
                pass

            mock_dendrite.aclose_session.assert_called_once()
