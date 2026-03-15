"""Tests for lifespan startup/shutdown behavior.

Uses real Postgres and Redis (per CLAUDE.md). Only Bittensor SDK is mocked.
Tests that exercise the Bittensor code path must override enable_bittensor=True
since CI sets ENABLE_BITTENSOR=false.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.subnets.registry import AdapterRegistry


def _bt_settings_patch():
    """Patch settings to enable Bittensor and provide all required config."""
    mock = MagicMock()
    mock.enable_bittensor = True
    mock.app_version = "0.0.0-test"
    mock.metagraph_sync_interval_seconds = 120
    mock.dendrite_timeout_seconds = 30
    mock.sn1_netuid = 1
    mock.sn19_netuid = 19
    mock.sn62_netuid = 62
    mock.sn19_timeout_seconds = 90
    mock.sn62_timeout_seconds = 30
    mock.score_ema_alpha = 0.3
    mock.quality_sample_rate = 0.1
    mock.quality_weight = 0.3
    mock.score_flush_interval_seconds = 60
    mock.score_retention_days = 30
    mock.usage_aggregation_interval_seconds = 86400
    mock.usage_retention_days = 90
    mock.debug_log_cleanup_interval_seconds = 3600
    mock.debug_log_retention_hours = 48
    return patch("gateway.main.settings", mock)


class TestLifespanBittensorDisabled:
    """Test that lifespan succeeds without Bittensor when disabled."""

    @pytest.mark.asyncio
    async def test_startup_succeeds_without_bittensor(self) -> None:
        """When enable_bittensor=False, gateway starts with real DB/Redis but no wallet."""
        with patch("gateway.main.settings") as mock_settings:
            mock_settings.enable_bittensor = False
            mock_settings.app_version = "0.0.0-test"
            mock_settings.usage_aggregation_interval_seconds = 86400
            mock_settings.usage_retention_days = 90
            mock_settings.debug_log_cleanup_interval_seconds = 3600
            mock_settings.debug_log_retention_hours = 48

            from fastapi import FastAPI

            from gateway.main import lifespan

            test_app = FastAPI()
            async with lifespan(test_app):
                assert test_app.state.dendrite is None
                assert test_app.state.miner_selector is None
                assert isinstance(test_app.state.adapter_registry, AdapterRegistry)


class TestLifespanStartupFailure:
    """Test that lifespan aborts when Bittensor init fails."""

    @pytest.mark.asyncio
    async def test_startup_raises_when_initial_metagraph_empty(self) -> None:
        """If initial sync completes but metagraph is still None, startup must fail."""
        mock_subtensor = MagicMock()
        mock_subtensor.metagraph.side_effect = ConnectionError("chain unreachable")

        with (
            _bt_settings_patch(),
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
            _bt_settings_patch(),
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


class TestLifespanShutdown:
    """Test that shutdown cleans up Bittensor resources with real DB/Redis."""

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
            _bt_settings_patch(),
            patch("gateway.main.create_wallet", return_value=MagicMock()),
            patch("gateway.main.create_subtensor", return_value=mock_subtensor),
            patch("gateway.main.create_dendrite", return_value=mock_dendrite),
        ):
            from fastapi import FastAPI

            from gateway.main import lifespan

            test_app = FastAPI()
            async with lifespan(test_app):
                pass

            mock_dendrite.aclose_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_continues_after_metagraph_stop_failure(self) -> None:
        """If metagraph_manager.stop() raises, shutdown still completes."""
        mock_subtensor = MagicMock()
        mock_metagraph = MagicMock()
        mock_metagraph.n = 0
        mock_subtensor.metagraph.return_value = mock_metagraph

        mock_dendrite = MagicMock()
        mock_dendrite.aclose_session = AsyncMock()

        with (
            _bt_settings_patch(),
            patch("gateway.main.create_wallet", return_value=MagicMock()),
            patch("gateway.main.create_subtensor", return_value=mock_subtensor),
            patch("gateway.main.create_dendrite", return_value=mock_dendrite),
            patch(
                "gateway.main.MetagraphManager.stop",
                new_callable=AsyncMock,
                side_effect=RuntimeError("stop failed"),
            ),
        ):
            from fastapi import FastAPI

            from gateway.main import lifespan

            test_app = FastAPI()
            async with lifespan(test_app):
                pass

            mock_dendrite.aclose_session.assert_called_once()
