"""Unit tests สำหรับ ServiceTokenProvider — mock Identity Service ด้วย httpx.MockTransport"""
import asyncio
import base64
import json

import httpx
import pytest

from src.auth.service_token import ServiceTokenError, ServiceTokenProvider

TOKEN_URL = "http://identity.test/token"


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _identity(calls: list, *, expires_in=3600, status=200, body=None) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if status != 200:
            return httpx.Response(status, json={"detail": "nope"})
        payload = body if body is not None else {
            "access_token": f"tok-{len(calls)}",
            "token_type": "Bearer",
            "expires_in": expires_in,
            "scope": "knowledge:read",
        }
        return httpx.Response(200, json=payload)

    return httpx.MockTransport(handler)


def _provider(transport, clock=None, secret="s3cret", **kwargs) -> ServiceTokenProvider:
    return ServiceTokenProvider(
        TOKEN_URL, "nova-studio", secret, ["knowledge:read"],
        transport=transport, clock=clock or FakeClock(), **kwargs,
    )


@pytest.mark.asyncio
async def test_requests_token_with_basic_auth_and_json_scopes():
    calls: list = []
    provider = _provider(_identity(calls))

    assert await provider.get_token() == "tok-1"

    request = calls[0]
    assert request.method == "POST"
    assert str(request.url) == TOKEN_URL
    expected = "Basic " + base64.b64encode(b"nova-studio:s3cret").decode()
    assert request.headers["authorization"] == expected
    assert json.loads(request.content) == {"scopes": ["knowledge:read"]}


@pytest.mark.asyncio
async def test_token_is_cached_between_calls():
    calls: list = []
    provider = _provider(_identity(calls))

    assert await provider.get_token() == "tok-1"
    assert await provider.get_token() == "tok-1"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_token_is_refreshed_before_it_expires():
    calls: list = []
    clock = FakeClock()
    provider = _provider(_identity(calls, expires_in=3600), clock=clock)  # margin 60s

    assert await provider.get_token() == "tok-1"
    clock.now += 3539  # still more than the margin left
    assert await provider.get_token() == "tok-1"
    clock.now += 2  # inside the margin -> refresh
    assert await provider.get_token() == "tok-2"
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_short_lived_token_is_refreshed_at_half_life():
    calls: list = []
    clock = FakeClock()
    provider = _provider(_identity(calls, expires_in=30), clock=clock)

    assert await provider.get_token() == "tok-1"
    clock.now += 14
    assert await provider.get_token() == "tok-1"
    clock.now += 2
    assert await provider.get_token() == "tok-2"


@pytest.mark.asyncio
async def test_invalidate_forces_a_new_token():
    calls: list = []
    provider = _provider(_identity(calls))

    assert await provider.get_token() == "tok-1"
    provider.invalidate()
    assert await provider.get_token() == "tok-2"


@pytest.mark.asyncio
async def test_invalidating_an_old_token_keeps_the_newer_one():
    calls: list = []
    provider = _provider(_identity(calls))

    assert await provider.get_token() == "tok-1"
    provider.invalidate()
    assert await provider.get_token() == "tok-2"
    provider.invalidate("tok-1")  # late 401 for the old token
    assert await provider.get_token() == "tok-2"
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_identity_error_status_raises_without_leaking_secret():
    calls: list = []
    provider = _provider(_identity(calls, status=401), secret="topsecret")

    with pytest.raises(ServiceTokenError) as exc_info:
        await provider.get_token()

    assert "401" in str(exc_info.value)
    assert "topsecret" not in str(exc_info.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        {"expires_in": 3600},
        {"access_token": "x"},
        {"access_token": "", "expires_in": 3600},
        {"access_token": "x", "expires_in": 0},
        {"access_token": "x", "expires_in": "abc"},
        ["not", "a", "dict"],
    ],
)
async def test_malformed_token_response_raises(body):
    provider = _provider(_identity([], body=body))

    with pytest.raises(ServiceTokenError):
        await provider.get_token()


@pytest.mark.asyncio
async def test_network_failure_raises_service_token_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    provider = _provider(httpx.MockTransport(handler))

    with pytest.raises(ServiceTokenError) as exc_info:
        await provider.get_token()

    assert "ConnectError" in str(exc_info.value)


@pytest.mark.asyncio
async def test_missing_secret_raises_without_calling_identity():
    calls: list = []
    provider = _provider(_identity(calls), secret="")

    with pytest.raises(ServiceTokenError):
        await provider.get_token()

    assert calls == []


@pytest.mark.asyncio
async def test_concurrent_callers_share_a_single_refresh():
    calls: list = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        await asyncio.sleep(0.01)
        return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})

    provider = _provider(httpx.MockTransport(handler))

    tokens = await asyncio.gather(*[provider.get_token() for _ in range(5)])

    assert tokens == ["tok"] * 5
    assert len(calls) == 1
