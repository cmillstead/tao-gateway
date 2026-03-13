"""Tests for Bittensor SDK initialization and configuration."""

import logging
from unittest.mock import MagicMock, patch

import pytest

from gateway.core.bittensor import create_dendrite, create_subtensor, create_wallet
from gateway.core.config import Settings


class TestBittensorSettings:
    """Test that Bittensor configuration settings are present and have correct defaults."""

    def test_hotkey_name_default(self) -> None:
        s = Settings(jwt_secret_key="a" * 32, debug=True)
        assert s.hotkey_name == "default"

    def test_sn1_netuid_default(self) -> None:
        s = Settings(jwt_secret_key="a" * 32, debug=True)
        assert s.sn1_netuid == 1

    def test_metagraph_sync_interval_default(self) -> None:
        s = Settings(jwt_secret_key="a" * 32, debug=True)
        assert s.metagraph_sync_interval_seconds == 120

    def test_dendrite_timeout_default(self) -> None:
        s = Settings(jwt_secret_key="a" * 32, debug=True)
        assert s.dendrite_timeout_seconds == 30

    def test_subtensor_network_default(self) -> None:
        s = Settings(jwt_secret_key="a" * 32, debug=True)
        assert s.subtensor_network == "finney"


class TestCreateWallet:
    """Test wallet creation from configuration."""

    @patch("gateway.core.bittensor.bt")
    def test_creates_wallet_with_settings(self, mock_bt: MagicMock) -> None:
        mock_wallet = MagicMock()
        mock_bt.Wallet.return_value = mock_wallet

        result = create_wallet()
        mock_bt.Wallet.assert_called_once()
        assert result is mock_wallet

    @patch("gateway.core.bittensor.bt")
    def test_wallet_no_key_material_logged(
        self, mock_bt: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        mock_wallet = MagicMock()
        mock_wallet.coldkey = "SECRET_COLDKEY"
        mock_wallet.hotkey = "SECRET_HOTKEY"
        mock_bt.Wallet.return_value = mock_wallet

        with caplog.at_level(logging.DEBUG):
            create_wallet()
        log_text = caplog.text
        assert "SECRET_COLDKEY" not in log_text
        assert "SECRET_HOTKEY" not in log_text


class TestCreateSubtensor:
    """Test subtensor connection creation."""

    @patch("gateway.core.bittensor.bt")
    def test_creates_subtensor(self, mock_bt: MagicMock) -> None:
        mock_subtensor = MagicMock()
        mock_bt.Subtensor.return_value = mock_subtensor

        result = create_subtensor()
        mock_bt.Subtensor.assert_called_once()
        assert result is mock_subtensor


class TestCreateDendrite:
    """Test dendrite client creation."""

    @patch("gateway.core.bittensor.bt")
    def test_creates_dendrite_from_wallet(self, mock_bt: MagicMock) -> None:
        mock_wallet = MagicMock()
        mock_dendrite = MagicMock()
        mock_bt.Dendrite.return_value = mock_dendrite

        result = create_dendrite(mock_wallet)
        mock_bt.Dendrite.assert_called_once_with(wallet=mock_wallet)
        assert result is mock_dendrite


class TestInitFailures:
    """Test graceful failure handling during SDK initialization."""

    @patch("gateway.core.bittensor.bt")
    def test_wallet_creation_failure_raises(self, mock_bt: MagicMock) -> None:
        mock_bt.Wallet.side_effect = FileNotFoundError("wallet not found")

        with pytest.raises(FileNotFoundError):
            create_wallet()

    @patch("gateway.core.bittensor.bt")
    def test_subtensor_creation_failure_raises(self, mock_bt: MagicMock) -> None:
        mock_bt.Subtensor.side_effect = ConnectionError("network unreachable")

        with pytest.raises(ConnectionError):
            create_subtensor()
