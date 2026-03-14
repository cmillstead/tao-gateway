from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from gateway.core.config import settings
from gateway.subnets.registry import AdapterRegistry
from tests.api.conftest import get_api_key


async def _get_api_key(client: AsyncClient) -> str:
    return await get_api_key(client, "codetest@example.com")


def _make_success_synapse(
    code: str = "def hello():\n    print('Hello')",
    completion_language: str = "python",
):
    synapse = MagicMock()
    synapse.code = code
    synapse.completion_language = completion_language
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
async def test_code_completion_success(
    client: AsyncClient, test_app: FastAPI
) -> None:
    api_key = await _get_api_key(client)
    _setup_miner_selector(test_app)

    mock_dendrite = AsyncMock()
    mock_dendrite.forward.return_value = [_make_success_synapse()]
    test_app.state.dendrite = mock_dendrite

    response = await client.post(
        "/v1/code/completions",
        json={"model": "tao-sn62", "prompt": "Write hello world", "language": "python"},
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "code.completion"
    assert data["model"] == "tao-sn62"
    assert data["id"].startswith("codecmpl-")
    assert "created" in data
    assert len(data["choices"]) == 1
    assert data["choices"][0]["code"] == "def hello():\n    print('Hello')"
    assert data["choices"][0]["language"] == "python"
    assert data["choices"][0]["finish_reason"] == "stop"

    # Verify gateway headers
    assert "x-taogateway-miner-uid" in response.headers
    assert "x-taogateway-latency-ms" in response.headers
    assert "x-taogateway-subnet" in response.headers
    assert response.headers["x-taogateway-subnet"] == "sn62"


@pytest.mark.asyncio
async def test_code_completion_with_context(
    client: AsyncClient, test_app: FastAPI
) -> None:
    api_key = await _get_api_key(client)
    _setup_miner_selector(test_app)

    mock_dendrite = AsyncMock()
    mock_dendrite.forward.return_value = [_make_success_synapse()]
    test_app.state.dendrite = mock_dendrite

    response = await client.post(
        "/v1/code/completions",
        json={
            "model": "tao-sn62",
            "prompt": "Add error handling",
            "language": "python",
            "context": "def process(data): return data.strip()",
        },
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_code_completion_422_missing_prompt(
    client: AsyncClient, test_app: FastAPI
) -> None:
    api_key = await _get_api_key(client)

    response = await client.post(
        "/v1/code/completions",
        json={"model": "tao-sn62", "language": "python"},
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_code_completion_422_missing_language(
    client: AsyncClient, test_app: FastAPI
) -> None:
    api_key = await _get_api_key(client)

    response = await client.post(
        "/v1/code/completions",
        json={"model": "tao-sn62", "prompt": "Write hello world"},
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_code_completion_422_empty_prompt(
    client: AsyncClient, test_app: FastAPI
) -> None:
    api_key = await _get_api_key(client)

    response = await client.post(
        "/v1/code/completions",
        json={"model": "tao-sn62", "prompt": "", "language": "python"},
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_code_completion_422_empty_language(
    client: AsyncClient, test_app: FastAPI
) -> None:
    api_key = await _get_api_key(client)

    response = await client.post(
        "/v1/code/completions",
        json={"model": "tao-sn62", "prompt": "Write code", "language": ""},
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_code_completion_401_without_auth(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/code/completions",
        json={"model": "tao-sn62", "prompt": "Write code", "language": "python"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_code_completion_503_no_adapter(
    client: AsyncClient, test_app: FastAPI
) -> None:
    api_key = await _get_api_key(client)

    # Use empty adapter registry
    test_app.state.adapter_registry = AdapterRegistry()

    response = await client.post(
        "/v1/code/completions",
        json={"model": "tao-sn62", "prompt": "Write code", "language": "python"},
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_code_completion_504_miner_timeout(
    client: AsyncClient, test_app: FastAPI
) -> None:
    api_key = await _get_api_key(client)
    _setup_miner_selector(test_app)

    mock_dendrite = AsyncMock()
    mock_dendrite.forward.return_value = [_make_timeout_synapse()]
    test_app.state.dendrite = mock_dendrite

    response = await client.post(
        "/v1/code/completions",
        json={"model": "tao-sn62", "prompt": "Write code", "language": "python"},
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 504


@pytest.mark.asyncio
async def test_code_completion_502_empty_code(
    client: AsyncClient, test_app: FastAPI
) -> None:
    api_key = await _get_api_key(client)
    _setup_miner_selector(test_app)

    mock_dendrite = AsyncMock()
    mock_dendrite.forward.return_value = [_make_success_synapse(code="")]
    test_app.state.dendrite = mock_dendrite

    response = await client.post(
        "/v1/code/completions",
        json={"model": "tao-sn62", "prompt": "Write code", "language": "python"},
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 502


@pytest.mark.asyncio
async def test_code_completion_preserves_code_with_angle_brackets(
    client: AsyncClient, test_app: FastAPI
) -> None:
    """Code must not be HTML-sanitized — angle brackets are valid in code."""
    api_key = await _get_api_key(client)
    _setup_miner_selector(test_app)

    code_with_angles = "if n <= 1:\n    return n"
    mock_dendrite = AsyncMock()
    mock_dendrite.forward.return_value = [
        _make_success_synapse(code=code_with_angles)
    ]
    test_app.state.dendrite = mock_dendrite

    response = await client.post(
        "/v1/code/completions",
        json={"model": "tao-sn62", "prompt": "Write code", "language": "python"},
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 200
    data = response.json()
    # Code must pass through untouched — no &lt; or &gt; encoding
    assert data["choices"][0]["code"] == code_with_angles


@pytest.mark.asyncio
async def test_code_completion_sanitizes_language_field(
    client: AsyncClient, test_app: FastAPI
) -> None:
    """Language label IS sanitized (simple text, not code)."""
    api_key = await _get_api_key(client)
    _setup_miner_selector(test_app)

    mock_dendrite = AsyncMock()
    mock_dendrite.forward.return_value = [
        _make_success_synapse(
            code="x = 1",
            completion_language='<script>evil()</script>python',
        )
    ]
    test_app.state.dendrite = mock_dendrite

    response = await client.post(
        "/v1/code/completions",
        json={"model": "tao-sn62", "prompt": "Write code", "language": "python"},
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 200
    data = response.json()
    lang = data["choices"][0]["language"]
    assert "<script>" not in lang
    assert "python" in lang


@pytest.mark.asyncio
async def test_code_completion_502_dendrite_network_error(
    client: AsyncClient, test_app: FastAPI
) -> None:
    api_key = await _get_api_key(client)
    _setup_miner_selector(test_app)

    mock_dendrite = AsyncMock()
    mock_dendrite.forward.side_effect = ConnectionError("Miner unreachable")
    test_app.state.dendrite = mock_dendrite

    response = await client.post(
        "/v1/code/completions",
        json={"model": "tao-sn62", "prompt": "Write code", "language": "python"},
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 502


@pytest.mark.asyncio
async def test_code_completion_502_dendrite_timeout_error(
    client: AsyncClient, test_app: FastAPI
) -> None:
    api_key = await _get_api_key(client)
    _setup_miner_selector(test_app)

    mock_dendrite = AsyncMock()
    mock_dendrite.forward.side_effect = TimeoutError("Dendrite timeout")
    test_app.state.dendrite = mock_dendrite

    response = await client.post(
        "/v1/code/completions",
        json={"model": "tao-sn62", "prompt": "Write code", "language": "python"},
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 504


@pytest.mark.asyncio
async def test_code_completion_429_rate_limit(
    client: AsyncClient, test_app: FastAPI
) -> None:
    api_key = await _get_api_key(client)
    _setup_miner_selector(test_app)

    mock_dendrite = AsyncMock()
    mock_dendrite.forward.return_value = [_make_success_synapse()]
    test_app.state.dendrite = mock_dendrite

    # Exhaust rate limit (SN62 free tier: 10 req/min)
    from gateway.middleware.rate_limit import get_subnet_rate_limits

    sn62_limits = get_subnet_rate_limits(settings.sn62_netuid)
    for _ in range(sn62_limits["minute"]):
        resp = await client.post(
            "/v1/code/completions",
            json={"model": "tao-sn62", "prompt": "Write code", "language": "python"},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert resp.status_code == 200

    # Next request should be rate limited
    response = await client.post(
        "/v1/code/completions",
        json={"model": "tao-sn62", "prompt": "Write code", "language": "python"},
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 429
