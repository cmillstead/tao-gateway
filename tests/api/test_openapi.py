import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_openapi_json_returns_valid_spec(client: AsyncClient) -> None:
    """GET /openapi.json returns a valid OpenAPI 3.x spec."""
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    assert "openapi" in spec
    assert spec["openapi"].startswith("3.")
    assert "paths" in spec
    assert "components" in spec
    # Verify key dashboard endpoints are present
    assert "/dashboard/api-keys" in spec["paths"]
    assert "/dashboard/overview" in spec["paths"]
    assert "/auth/signup" in spec["paths"]
