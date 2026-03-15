import pytest
from httpx import AsyncClient


async def _signup_and_get_jwt(client: AsyncClient, email: str) -> str:
    """Helper: signup + login, return JWT token."""
    await client.post(
        "/auth/signup",
        json={"email": email, "password": "securepassword123"},
    )
    response = await client.post(
        "/auth/login",
        json={"email": email, "password": "securepassword123"},
    )
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_create_api_key_returns_full_key(client: AsyncClient) -> None:
    token = await _signup_and_get_jwt(client, "keytest@example.com")
    response = await client.post(
        "/dashboard/api-keys",
        json={"environment": "live"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["key"].startswith("tao_sk_live_")
    assert "prefix" in data
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_test_key(client: AsyncClient) -> None:
    token = await _signup_and_get_jwt(client, "testkey@example.com")
    response = await client.post(
        "/dashboard/api-keys",
        json={"environment": "test"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    assert response.json()["key"].startswith("tao_sk_test_")


@pytest.mark.asyncio
async def test_list_api_keys_masked(client: AsyncClient) -> None:
    token = await _signup_and_get_jwt(client, "listkeys@example.com")
    # Create a key first
    create_response = await client.post(
        "/dashboard/api-keys",
        json={"environment": "live"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.json()["key"].startswith("tao_sk_live_")  # full key returned at creation

    # List keys — should not contain full key
    response = await client.get(
        "/dashboard/api-keys",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1
    for key in data["items"]:
        assert "prefix" in key
        assert "key" not in key  # Full key should NOT be in list response
        assert "is_active" in key


@pytest.mark.asyncio
async def test_create_api_key_unauthenticated(client: AsyncClient) -> None:
    response = await client.post(
        "/dashboard/api-keys",
        json={"environment": "live"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_revoke_api_key(client: AsyncClient) -> None:
    token = await _signup_and_get_jwt(client, "revoke@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    create_resp = await client.post(
        "/dashboard/api-keys",
        json={"environment": "live"},
        headers=headers,
    )
    key_id = create_resp.json()["id"]

    revoke_resp = await client.delete(
        f"/dashboard/api-keys/{key_id}",
        headers=headers,
    )
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["message"] == "API key revoked"

    # Verify revoked key is excluded from default listing
    list_resp = await client.get("/dashboard/api-keys", headers=headers)
    keys = list_resp.json()["items"]
    assert not any(k["id"] == key_id for k in keys)


@pytest.mark.asyncio
async def test_revoke_nonexistent_key_returns_404(client: AsyncClient) -> None:
    token = await _signup_and_get_jwt(client, "revoke404@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.delete(
        "/dashboard/api-keys/00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_revoke_other_orgs_key_returns_404(client: AsyncClient) -> None:
    """Org A cannot revoke org B's key (cross-tenant isolation)."""
    token_a = await _signup_and_get_jwt(client, "org_a@example.com")
    token_b = await _signup_and_get_jwt(client, "org_b@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Org B creates a key
    create_resp = await client.post(
        "/dashboard/api-keys",
        json={"environment": "live"},
        headers=headers_b,
    )
    key_id_b = create_resp.json()["id"]

    # Org A tries to revoke org B's key
    revoke_resp = await client.delete(
        f"/dashboard/api-keys/{key_id_b}",
        headers=headers_a,
    )
    assert revoke_resp.status_code == 404

    # Verify key is still active for org B
    list_resp = await client.get("/dashboard/api-keys", headers=headers_b)
    keys = list_resp.json()["items"]
    assert any(k["id"] == key_id_b and k["is_active"] for k in keys)


@pytest.mark.asyncio
async def test_list_api_keys_pagination_bounds(client: AsyncClient) -> None:
    """Pagination params are validated: limit must be 1-100, offset >= 0."""
    token = await _signup_and_get_jwt(client, "pagination@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get("/dashboard/api-keys?limit=0", headers=headers)
    assert resp.status_code == 422

    resp = await client.get("/dashboard/api-keys?limit=101", headers=headers)
    assert resp.status_code == 422

    resp = await client.get("/dashboard/api-keys?offset=-1", headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_api_key_with_name(client: AsyncClient) -> None:
    """Creating a key with a custom name persists and returns it."""
    token = await _signup_and_get_jwt(client, "keyname@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.post(
        "/dashboard/api-keys",
        json={"environment": "live", "name": "production"},
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "production"


@pytest.mark.asyncio
async def test_create_api_key_without_name_auto_generates(
    client: AsyncClient,
) -> None:
    """Creating a key without a name auto-generates 'Key N'."""
    token = await _signup_and_get_jwt(client, "autoname@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    resp1 = await client.post(
        "/dashboard/api-keys",
        json={"environment": "live"},
        headers=headers,
    )
    assert resp1.status_code == 201
    assert resp1.json()["name"] == "Key 1"

    resp2 = await client.post(
        "/dashboard/api-keys",
        json={"environment": "live"},
        headers=headers,
    )
    assert resp2.status_code == 201
    assert resp2.json()["name"] == "Key 2"


@pytest.mark.asyncio
async def test_list_api_keys_includes_name(client: AsyncClient) -> None:
    """List response includes the name field."""
    token = await _signup_and_get_jwt(client, "listname@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(
        "/dashboard/api-keys",
        json={"environment": "live", "name": "my-key"},
        headers=headers,
    )
    resp = await client.get("/dashboard/api-keys", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    assert items[0]["name"] == "my-key"


@pytest.mark.asyncio
async def test_rotate_api_key_creates_new_revokes_old(
    client: AsyncClient,
) -> None:
    """Rotation creates a new key and revokes the old one atomically."""
    token = await _signup_and_get_jwt(client, "rotate@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    create_resp = await client.post(
        "/dashboard/api-keys",
        json={"environment": "live", "name": "rotatable"},
        headers=headers,
    )
    old_key_id = create_resp.json()["id"]

    rotate_resp = await client.post(
        f"/dashboard/api-keys/rotate/{old_key_id}",
        headers=headers,
    )
    assert rotate_resp.status_code == 201
    data = rotate_resp.json()
    assert data["revoked_key_id"] == old_key_id
    assert data["new_key"]["key"].startswith("tao_sk_live_")
    assert data["new_key"]["name"] == "rotatable"
    assert data["new_key"]["id"] != old_key_id


@pytest.mark.asyncio
async def test_rotate_api_key_returns_full_new_key(
    client: AsyncClient,
) -> None:
    """Rotation response contains the full new key (shown once)."""
    token = await _signup_and_get_jwt(client, "rotatefull@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    create_resp = await client.post(
        "/dashboard/api-keys",
        json={"environment": "test"},
        headers=headers,
    )
    old_id = create_resp.json()["id"]

    rotate_resp = await client.post(
        f"/dashboard/api-keys/rotate/{old_id}",
        headers=headers,
    )
    new_key = rotate_resp.json()["new_key"]["key"]
    assert new_key.startswith("tao_sk_test_")
    assert len(new_key) > 20


@pytest.mark.asyncio
async def test_rotate_nonexistent_key_returns_404(
    client: AsyncClient,
) -> None:
    token = await _signup_and_get_jwt(client, "rotatemissing@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post(
        "/dashboard/api-keys/rotate/00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_rotate_revoked_key_returns_404(
    client: AsyncClient,
) -> None:
    """Cannot rotate an already-revoked key."""
    token = await _signup_and_get_jwt(client, "rotaterevoked@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    create_resp = await client.post(
        "/dashboard/api-keys",
        json={"environment": "live"},
        headers=headers,
    )
    key_id = create_resp.json()["id"]

    # Revoke the key first
    await client.delete(
        f"/dashboard/api-keys/{key_id}", headers=headers,
    )

    # Try to rotate the revoked key
    resp = await client.post(
        f"/dashboard/api-keys/rotate/{key_id}",
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_api_keys_with_include_revoked(
    client: AsyncClient,
) -> None:
    """include_revoked=true shows revoked keys in listing."""
    token = await _signup_and_get_jwt(client, "includerevoked@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    create_resp = await client.post(
        "/dashboard/api-keys",
        json={"environment": "live"},
        headers=headers,
    )
    key_id = create_resp.json()["id"]
    await client.delete(
        f"/dashboard/api-keys/{key_id}", headers=headers,
    )

    # Default excludes revoked
    resp_default = await client.get(
        "/dashboard/api-keys", headers=headers,
    )
    assert not any(
        k["id"] == key_id for k in resp_default.json()["items"]
    )

    # With include_revoked=true
    resp_revoked = await client.get(
        "/dashboard/api-keys?include_revoked=true",
        headers=headers,
    )
    items = resp_revoked.json()["items"]
    revoked = [k for k in items if k["id"] == key_id]
    assert len(revoked) == 1
    assert revoked[0]["is_active"] is False


@pytest.mark.asyncio
async def test_list_api_keys_default_excludes_revoked(
    client: AsyncClient,
) -> None:
    """Default listing (no include_revoked) hides revoked keys."""
    token = await _signup_and_get_jwt(client, "defaultrevoked@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    create_resp = await client.post(
        "/dashboard/api-keys",
        json={"environment": "live"},
        headers=headers,
    )
    key_id = create_resp.json()["id"]
    await client.delete(
        f"/dashboard/api-keys/{key_id}", headers=headers,
    )

    resp = await client.get("/dashboard/api-keys", headers=headers)
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_rotate_other_orgs_key_returns_404(
    client: AsyncClient,
) -> None:
    """Org A cannot rotate org B's key (cross-tenant isolation)."""
    token_a = await _signup_and_get_jwt(client, "rot_org_a@example.com")
    token_b = await _signup_and_get_jwt(client, "rot_org_b@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    create_resp = await client.post(
        "/dashboard/api-keys",
        json={"environment": "live"},
        headers=headers_b,
    )
    key_id_b = create_resp.json()["id"]

    resp = await client.post(
        f"/dashboard/api-keys/rotate/{key_id_b}",
        headers=headers_a,
    )
    assert resp.status_code == 404

    # Verify key is still active for org B
    list_resp = await client.get("/dashboard/api-keys", headers=headers_b)
    keys = list_resp.json()["items"]
    assert any(k["id"] == key_id_b and k["is_active"] for k in keys)


@pytest.mark.asyncio
async def test_create_api_key_name_too_long_returns_422(
    client: AsyncClient,
) -> None:
    """Name exceeding 100 characters is rejected."""
    token = await _signup_and_get_jwt(client, "longname@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post(
        "/dashboard/api-keys",
        json={"environment": "live", "name": "x" * 101},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_api_key_empty_name_auto_generates(
    client: AsyncClient,
) -> None:
    """Empty string name triggers auto-generation."""
    token = await _signup_and_get_jwt(client, "emptyname@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post(
        "/dashboard/api-keys",
        json={"environment": "live", "name": ""},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Key 1"


@pytest.mark.asyncio
async def test_create_api_key_rejects_when_limit_reached(client: AsyncClient) -> None:
    """Creating more than MAX_KEYS_PER_ORG active keys returns 422."""
    from unittest.mock import patch

    token = await _signup_and_get_jwt(client, "keylimit@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    with patch("gateway.services.api_key_service.MAX_KEYS_PER_ORG", 3):
        for i in range(3):
            resp = await client.post(
                "/dashboard/api-keys",
                json={"environment": "test"},
                headers=headers,
            )
            assert resp.status_code == 201, f"Key {i+1} failed: {resp.text}"

        resp = await client.post(
            "/dashboard/api-keys",
            json={"environment": "test"},
            headers=headers,
        )
        assert resp.status_code == 422
        assert "Maximum" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_list_api_keys_includes_debug_mode(client: AsyncClient) -> None:
    """List response includes the debug_mode field, defaults to false."""
    token = await _signup_and_get_jwt(client, "debuglist@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(
        "/dashboard/api-keys",
        json={"environment": "live"},
        headers=headers,
    )
    resp = await client.get("/dashboard/api-keys", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    assert items[0]["debug_mode"] is False


@pytest.mark.asyncio
async def test_patch_api_key_toggle_debug_mode(client: AsyncClient) -> None:
    """PATCH /dashboard/api-keys/{key_id} toggles debug_mode."""
    token = await _signup_and_get_jwt(client, "debugtoggle@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    create_resp = await client.post(
        "/dashboard/api-keys",
        json={"environment": "live"},
        headers=headers,
    )
    key_id = create_resp.json()["id"]

    # Enable debug mode
    resp = await client.patch(
        f"/dashboard/api-keys/{key_id}",
        json={"debug_mode": True},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["debug_mode"] is True

    # Disable debug mode
    resp = await client.patch(
        f"/dashboard/api-keys/{key_id}",
        json={"debug_mode": False},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["debug_mode"] is False


@pytest.mark.asyncio
async def test_patch_api_key_other_org_returns_404(client: AsyncClient) -> None:
    """Org A cannot toggle debug mode on org B's key."""
    token_a = await _signup_and_get_jwt(client, "debug_org_a@example.com")
    token_b = await _signup_and_get_jwt(client, "debug_org_b@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    create_resp = await client.post(
        "/dashboard/api-keys",
        json={"environment": "live"},
        headers=headers_b,
    )
    key_id_b = create_resp.json()["id"]

    resp = await client.patch(
        f"/dashboard/api-keys/{key_id_b}",
        json={"debug_mode": True},
        headers=headers_a,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_debug_logs_empty(client: AsyncClient) -> None:
    """GET /dashboard/api-keys/{key_id}/debug-logs returns empty list when no logs."""
    token = await _signup_and_get_jwt(client, "debuglogs@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    create_resp = await client.post(
        "/dashboard/api-keys",
        json={"environment": "live"},
        headers=headers,
    )
    key_id = create_resp.json()["id"]

    resp = await client.get(
        f"/dashboard/api-keys/{key_id}/debug-logs",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_get_debug_logs_returns_content(client: AsyncClient) -> None:
    """Debug logs with content are returned correctly via the API."""
    from sqlalchemy import select

    from gateway.core.database import get_session_factory
    from gateway.middleware.usage import record_usage
    from gateway.models.api_key import ApiKey

    token = await _signup_and_get_jwt(client, "debugcontent@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Create a key and enable debug mode
    create_resp = await client.post(
        "/dashboard/api-keys",
        json={"environment": "live"},
        headers=headers,
    )
    key_id = create_resp.json()["id"]
    await client.patch(
        f"/dashboard/api-keys/{key_id}",
        json={"debug_mode": True},
        headers=headers,
    )

    # Get the actual key record to find org_id
    session_factory = get_session_factory()
    import uuid
    async with session_factory() as session:
        key = await session.scalar(
            select(ApiKey).where(ApiKey.id == uuid.UUID(key_id))
        )
        assert key is not None
        org_id = key.org_id

    # Create a debug log entry via record_usage
    await record_usage(
        session_factory=session_factory,
        api_key_id=uuid.UUID(key_id),
        org_id=org_id,
        subnet_name="sn1",
        netuid=1,
        endpoint="/v1/chat/completions",
        miner_uid="test-miner",
        latency_ms=150,
        status_code=200,
        debug_mode=True,
        request_body='{"messages": [{"role": "user", "content": "hello"}]}',
        response_body='{"choices": [{"message": {"content": "hi"}}]}',
    )

    # Fetch debug logs and verify content
    resp = await client.get(
        f"/dashboard/api-keys/{key_id}/debug-logs",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    entry = data["items"][0]
    assert "messages" in entry["request_body"]
    assert "choices" in entry["response_body"]
    assert "created_at" in entry
    assert "id" in entry
    assert "usage_record_id" in entry


@pytest.mark.asyncio
async def test_get_debug_logs_other_org_returns_404(client: AsyncClient) -> None:
    """Org A cannot view debug logs for org B's key."""
    token_a = await _signup_and_get_jwt(client, "dl_org_a@example.com")
    token_b = await _signup_and_get_jwt(client, "dl_org_b@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    create_resp = await client.post(
        "/dashboard/api-keys",
        json={"environment": "live"},
        headers=headers_b,
    )
    key_id_b = create_resp.json()["id"]

    resp = await client.get(
        f"/dashboard/api-keys/{key_id_b}/debug-logs",
        headers=headers_a,
    )
    assert resp.status_code == 404
