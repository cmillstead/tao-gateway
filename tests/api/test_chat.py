from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import AsyncClient


async def _get_api_key(client: AsyncClient) -> str:
    """Helper: signup + login + create API key, return the raw key."""
    await client.post(
        "/auth/signup",
        json={"email": "chattest@example.com", "password": "securepassword123"},
    )
    login_resp = await client.post(
        "/auth/login",
        json={"email": "chattest@example.com", "password": "securepassword123"},
    )
    jwt = login_resp.json()["access_token"]
    key_resp = await client.post(
        "/dashboard/api-keys",
        json={"environment": "live"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    return key_resp.json()["key"]


def _make_success_synapse(
    completion: str = "Hello! I'm a decentralized AI.",
):
    synapse = MagicMock()
    synapse.completion = completion
    synapse.is_success = True
    synapse.is_timeout = False
    return synapse


def _make_timeout_synapse():
    synapse = MagicMock()
    synapse.is_success = False
    synapse.is_timeout = True
    return synapse


def _make_invalid_synapse():
    synapse = MagicMock()
    synapse.is_success = False
    synapse.is_timeout = False
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
async def test_chat_completion_success(
    client: AsyncClient, test_app: FastAPI
) -> None:
    api_key = await _get_api_key(client)
    _setup_miner_selector(test_app)

    mock_dendrite = AsyncMock()
    mock_dendrite.forward.return_value = [_make_success_synapse()]
    test_app.state.dendrite = mock_dendrite

    response = await client.post(
        "/v1/chat/completions",
        json={
            "model": "tao-sn1",
            "messages": [{"role": "user", "content": "Hello"}],
        },
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "chat.completion"
    assert data["model"] == "tao-sn1"
    assert data["choices"][0]["message"]["role"] == "assistant"
    expected = "Hello! I'm a decentralized AI."
    assert data["choices"][0]["message"]["content"] == expected
    assert data["choices"][0]["finish_reason"] == "stop"
    assert data["id"].startswith("chatcmpl-")
    assert isinstance(data["created"], int)
    assert data["usage"]["prompt_tokens"] == 0

    # Verify gateway headers
    assert "x-taogateway-miner-uid" in response.headers
    assert "x-taogateway-latency-ms" in response.headers
    assert response.headers["x-taogateway-subnet"] == "sn1"


@pytest.mark.asyncio
async def test_chat_completion_422_empty_messages(
    client: AsyncClient,
) -> None:
    api_key = await _get_api_key(client)

    response = await client.post(
        "/v1/chat/completions",
        json={"model": "tao-sn1", "messages": []},
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_chat_completion_422_missing_model(
    client: AsyncClient,
) -> None:
    api_key = await _get_api_key(client)

    response = await client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "Hello"}]},
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_chat_completion_422_no_user_message(
    client: AsyncClient,
) -> None:
    api_key = await _get_api_key(client)

    response = await client.post(
        "/v1/chat/completions",
        json={
            "model": "tao-sn1",
            "messages": [{"role": "system", "content": "Be helpful"}],
        },
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_chat_completion_504_miner_timeout(
    client: AsyncClient, test_app: FastAPI
) -> None:
    api_key = await _get_api_key(client)
    _setup_miner_selector(test_app)

    mock_dendrite = AsyncMock()
    mock_dendrite.forward.return_value = [_make_timeout_synapse()]
    test_app.state.dendrite = mock_dendrite

    response = await client.post(
        "/v1/chat/completions",
        json={
            "model": "tao-sn1",
            "messages": [{"role": "user", "content": "Hello"}],
        },
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 504
    data = response.json()
    assert data["error"]["type"] == "gateway_timeout"
    assert "miner_uid" in data["error"]


@pytest.mark.asyncio
async def test_chat_completion_502_invalid_miner_response(
    client: AsyncClient, test_app: FastAPI
) -> None:
    api_key = await _get_api_key(client)
    _setup_miner_selector(test_app)

    mock_dendrite = AsyncMock()
    mock_dendrite.forward.return_value = [_make_invalid_synapse()]
    test_app.state.dendrite = mock_dendrite

    response = await client.post(
        "/v1/chat/completions",
        json={
            "model": "tao-sn1",
            "messages": [{"role": "user", "content": "Hello"}],
        },
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 502
    data = response.json()
    assert data["error"]["type"] == "bad_gateway"


@pytest.mark.asyncio
async def test_chat_completion_503_subnet_unavailable(
    client: AsyncClient,
) -> None:
    api_key = await _get_api_key(client)

    response = await client.post(
        "/v1/chat/completions",
        json={
            "model": "nonexistent-model",
            "messages": [{"role": "user", "content": "Hello"}],
        },
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 503
    data = response.json()
    assert data["error"]["type"] == "subnet_unavailable"


@pytest.mark.asyncio
async def test_chat_completion_501_stream_true(
    client: AsyncClient,
) -> None:
    api_key = await _get_api_key(client)

    response = await client.post(
        "/v1/chat/completions",
        json={
            "model": "tao-sn1",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
        },
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 501
    data = response.json()
    assert data["error"]["type"] == "not_implemented"


@pytest.mark.asyncio
async def test_chat_completion_401_no_auth(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/chat/completions",
        json={
            "model": "tao-sn1",
            "messages": [{"role": "user", "content": "Hello"}],
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_chat_completion_response_openai_compatible(
    client: AsyncClient, test_app: FastAPI
) -> None:
    """Verify the response structure matches OpenAI ChatCompletion format."""
    api_key = await _get_api_key(client)
    _setup_miner_selector(test_app)

    mock_dendrite = AsyncMock()
    mock_dendrite.forward.return_value = [
        _make_success_synapse("Test response")
    ]
    test_app.state.dendrite = mock_dendrite

    response = await client.post(
        "/v1/chat/completions",
        json={
            "model": "tao-sn1",
            "messages": [{"role": "user", "content": "Hello"}],
        },
        headers={"Authorization": f"Bearer {api_key}"},
    )

    data = response.json()
    # All required OpenAI fields must be present
    assert "id" in data
    assert "object" in data
    assert "created" in data
    assert "model" in data
    assert "choices" in data
    assert "usage" in data
    assert "prompt_tokens" in data["usage"]
    assert "completion_tokens" in data["usage"]
    assert "total_tokens" in data["usage"]
