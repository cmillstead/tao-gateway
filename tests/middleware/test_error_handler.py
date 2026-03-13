"""Tests for the GatewayError exception handler."""

import json

import pytest
from fastapi import Request

from gateway.core.exceptions import (
    GatewayError,
    MinerInvalidResponseError,
    MinerTimeoutError,
)
from gateway.middleware.error_handler import gateway_exception_handler


def _fake_request() -> Request:
    scope = {"type": "http", "method": "GET", "path": "/test"}
    return Request(scope)


@pytest.mark.asyncio
async def test_includes_subnet_field():
    """MinerTimeoutError includes subnet in the response body."""
    exc = MinerTimeoutError(miner_uid="abc12345", subnet="sn1")
    response = await gateway_exception_handler(_fake_request(), exc)

    body = json.loads(response.body)
    assert body["error"]["subnet"] == "sn1"
    assert response.status_code == 504


@pytest.mark.asyncio
async def test_includes_miner_uid():
    """MinerInvalidResponseError includes miner_uid in the response body."""
    exc = MinerInvalidResponseError(miner_uid="def67890", subnet="sn1")
    response = await gateway_exception_handler(_fake_request(), exc)

    body = json.loads(response.body)
    assert body["error"]["miner_uid"] == "def67890"
    assert response.status_code == 502


@pytest.mark.asyncio
async def test_omits_optional_fields():
    """Base GatewayError without subnet/miner_uid omits those fields."""
    exc = GatewayError("Something broke", status_code=500)
    response = await gateway_exception_handler(_fake_request(), exc)

    body = json.loads(response.body)
    assert body["error"]["message"] == "Something broke"
    assert "subnet" not in body["error"]
    assert "miner_uid" not in body["error"]
    assert response.status_code == 500
