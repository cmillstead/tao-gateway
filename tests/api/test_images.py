import base64
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from gateway.subnets.registry import AdapterRegistry

# Minimal valid PNG for test responses
_PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24
_VALID_PNG_B64 = base64.b64encode(_PNG_HEADER).decode()


async def _get_api_key(client: AsyncClient) -> str:
    """Helper: signup + login + create API key, return the raw key."""
    await client.post(
        "/auth/signup",
        json={"email": "imagetest@example.com", "password": "securepassword123"},
    )
    login_resp = await client.post(
        "/auth/login",
        json={"email": "imagetest@example.com", "password": "securepassword123"},
    )
    jwt = login_resp.json()["access_token"]
    key_resp = await client.post(
        "/dashboard/api-keys",
        json={"environment": "live"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    return key_resp.json()["key"]


def _make_success_synapse(
    image_data: str = _VALID_PNG_B64,
    revised_prompt: str = "",
):
    synapse = MagicMock()
    synapse.image_data = image_data
    synapse.revised_prompt = revised_prompt
    synapse.is_success = True
    synapse.is_timeout = False
    return synapse


def _make_timeout_synapse():
    synapse = MagicMock()
    synapse.is_success = False
    synapse.is_timeout = True
    return synapse


def _setup_miner_selector(app: FastAPI) -> MagicMock:
    """Set up a mock miner selector that returns a valid axon."""
    mock_axon = MagicMock()
    mock_axon.hotkey = "test_hotkey_12345678"
    mock_selector = MagicMock()
    mock_selector.select_miner.return_value = mock_axon
    app.state.miner_selector = mock_selector
    return mock_selector


@pytest.mark.asyncio
async def test_image_generation_success(
    client: AsyncClient, test_app: FastAPI
) -> None:
    api_key = await _get_api_key(client)
    _setup_miner_selector(test_app)

    mock_dendrite = AsyncMock()
    mock_dendrite.forward.return_value = [_make_success_synapse()]
    test_app.state.dendrite = mock_dendrite

    response = await client.post(
        "/v1/images/generate",
        json={"model": "tao-sn19", "prompt": "A beautiful sunset"},
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "created" in data
    assert "data" in data
    assert len(data["data"]) == 1
    assert data["data"][0]["b64_json"] == _VALID_PNG_B64

    # Verify gateway headers
    assert "x-taogateway-miner-uid" in response.headers
    assert "x-taogateway-latency-ms" in response.headers
    assert "x-taogateway-subnet" in response.headers
    assert response.headers["x-taogateway-subnet"] == "sn19"


@pytest.mark.asyncio
async def test_image_generation_with_revised_prompt(
    client: AsyncClient, test_app: FastAPI
) -> None:
    api_key = await _get_api_key(client)
    _setup_miner_selector(test_app)

    mock_dendrite = AsyncMock()
    mock_dendrite.forward.return_value = [
        _make_success_synapse(revised_prompt="A stunning sunset over mountains")
    ]
    test_app.state.dendrite = mock_dendrite

    response = await client.post(
        "/v1/images/generate",
        json={"model": "tao-sn19", "prompt": "sunset"},
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"][0]["revised_prompt"] == "A stunning sunset over mountains"


@pytest.mark.asyncio
async def test_image_generation_422_missing_prompt(
    client: AsyncClient, test_app: FastAPI
) -> None:
    api_key = await _get_api_key(client)

    response = await client.post(
        "/v1/images/generate",
        json={"model": "tao-sn19"},
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_image_generation_422_empty_prompt(
    client: AsyncClient, test_app: FastAPI
) -> None:
    api_key = await _get_api_key(client)

    response = await client.post(
        "/v1/images/generate",
        json={"model": "tao-sn19", "prompt": ""},
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_image_generation_401_without_auth(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/images/generate",
        json={"model": "tao-sn19", "prompt": "A cat"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_image_generation_503_no_adapter(
    client: AsyncClient, test_app: FastAPI
) -> None:
    api_key = await _get_api_key(client)

    # Use empty adapter registry
    test_app.state.adapter_registry = AdapterRegistry()

    response = await client.post(
        "/v1/images/generate",
        json={"model": "tao-sn19", "prompt": "A cat"},
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_image_generation_504_miner_timeout(
    client: AsyncClient, test_app: FastAPI
) -> None:
    api_key = await _get_api_key(client)
    _setup_miner_selector(test_app)

    mock_dendrite = AsyncMock()
    mock_dendrite.forward.return_value = [_make_timeout_synapse()]
    test_app.state.dendrite = mock_dendrite

    response = await client.post(
        "/v1/images/generate",
        json={"model": "tao-sn19", "prompt": "A cat"},
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 504


@pytest.mark.asyncio
async def test_image_generation_502_invalid_response(
    client: AsyncClient, test_app: FastAPI
) -> None:
    api_key = await _get_api_key(client)
    _setup_miner_selector(test_app)

    # Miner returns non-image base64 data
    invalid_b64 = base64.b64encode(b"not an image").decode()
    mock_dendrite = AsyncMock()
    mock_dendrite.forward.return_value = [
        _make_success_synapse(image_data=invalid_b64)
    ]
    test_app.state.dendrite = mock_dendrite

    response = await client.post(
        "/v1/images/generate",
        json={"model": "tao-sn19", "prompt": "A cat"},
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 502


@pytest.mark.asyncio
async def test_image_generation_502_empty_image(
    client: AsyncClient, test_app: FastAPI
) -> None:
    api_key = await _get_api_key(client)
    _setup_miner_selector(test_app)

    mock_dendrite = AsyncMock()
    mock_dendrite.forward.return_value = [_make_success_synapse(image_data="")]
    test_app.state.dendrite = mock_dendrite

    response = await client.post(
        "/v1/images/generate",
        json={"model": "tao-sn19", "prompt": "A cat"},
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 502


@pytest.mark.asyncio
async def test_image_generation_sanitizes_revised_prompt(
    client: AsyncClient, test_app: FastAPI
) -> None:
    api_key = await _get_api_key(client)
    _setup_miner_selector(test_app)

    mock_dendrite = AsyncMock()
    mock_dendrite.forward.return_value = [
        _make_success_synapse(revised_prompt='<script>evil()</script>Clean text')
    ]
    test_app.state.dendrite = mock_dendrite

    response = await client.post(
        "/v1/images/generate",
        json={"model": "tao-sn19", "prompt": "test"},
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 200
    data = response.json()
    prompt = data["data"][0]["revised_prompt"]
    assert "<script>" not in prompt
    assert "Clean text" in prompt


@pytest.mark.asyncio
async def test_image_generation_422_invalid_size(
    client: AsyncClient, test_app: FastAPI
) -> None:
    api_key = await _get_api_key(client)

    response = await client.post(
        "/v1/images/generate",
        json={"model": "tao-sn19", "prompt": "A cat", "size": "banana"},
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_image_generation_422_invalid_style(
    client: AsyncClient, test_app: FastAPI
) -> None:
    api_key = await _get_api_key(client)

    response = await client.post(
        "/v1/images/generate",
        json={"model": "tao-sn19", "prompt": "A cat", "style": "abstract"},
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_image_generation_422_invalid_response_format(
    client: AsyncClient, test_app: FastAPI
) -> None:
    api_key = await _get_api_key(client)

    response = await client.post(
        "/v1/images/generate",
        json={"model": "tao-sn19", "prompt": "A cat", "response_format": "url"},
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_image_generation_502_dendrite_network_error(
    client: AsyncClient, test_app: FastAPI
) -> None:
    api_key = await _get_api_key(client)
    _setup_miner_selector(test_app)

    mock_dendrite = AsyncMock()
    mock_dendrite.forward.side_effect = ConnectionError("Miner unreachable")
    test_app.state.dendrite = mock_dendrite

    response = await client.post(
        "/v1/images/generate",
        json={"model": "tao-sn19", "prompt": "A cat"},
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 502
