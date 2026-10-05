"""Unit tests สำหรับ KnowledgeStudioClient — mock Knowledge Studio ด้วย httpx.MockTransport"""
import json

import httpx
import pytest

from src.auth.service_token import ServiceTokenError
from src.rag.knowledge_client import KnowledgeStudioClient, KnowledgeStudioError

# Shape returned by the real Knowledge Studio (POST /api/v1/knowledge/query)
KNOWLEDGE_RESULTS = [
    {
        "chunk_id": "c1",
        "document_id": "d1",
        "document_title": "Doc title",
        "text": "t",
        "score": 0.9,
    }
]
# What KnowledgeStudioClient hands to RAGService
MAPPED = [{"text": "t", "source": "Doc title", "score": 0.9}]


class FakeProvider:
    """Hands out tokens in order; invalidate() moves on to the next one."""

    def __init__(self, tokens: list[str]) -> None:
        self._tokens = tokens
        self._index = 0
        self.get_calls = 0
        self.invalidated: list = []

    async def get_token(self) -> str:
        self.get_calls += 1
        return self._tokens[self._index]

    def invalidate(self, token=None) -> None:
        self.invalidated.append(token)
        if token is None or token == self._tokens[self._index]:
            self._index = min(self._index + 1, len(self._tokens) - 1)


class RaisingProvider:
    async def get_token(self) -> str:
        raise ServiceTokenError("no token")

    def invalidate(self, token=None) -> None:
        pass


def _knowledge(calls: list, responder) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return responder(request)

    return httpx.MockTransport(handler)


def _ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"query": "q", "results": KNOWLEDGE_RESULTS})


def _client(transport, provider=None) -> KnowledgeStudioClient:
    return KnowledgeStudioClient(
        "http://knowledge.test/", token_provider=provider, transport=transport
    )


@pytest.mark.asyncio
async def test_uses_service_token_from_provider():
    calls: list = []
    provider = FakeProvider(["tok-A"])
    client = _client(_knowledge(calls, _ok), provider)

    results = await client.search("q", top_k=3)

    assert results == MAPPED
    request = calls[0]
    assert str(request.url) == "http://knowledge.test/api/v1/knowledge/query"
    assert request.headers["authorization"] == "Bearer tok-A"
    assert json.loads(request.content) == {"query": "q", "top_k": 3}


@pytest.mark.asyncio
async def test_explicit_auth_token_wins_and_provider_is_not_used():
    calls: list = []
    provider = FakeProvider(["tok-A"])
    client = _client(_knowledge(calls, _ok), provider)

    await client.search("q", auth_token="caller-token")

    assert calls[0].headers["authorization"] == "Bearer caller-token"
    assert provider.get_calls == 0


@pytest.mark.asyncio
async def test_without_provider_or_token_sends_no_authorization_header():
    calls: list = []
    client = _client(_knowledge(calls, _ok))

    await client.search("q")

    assert "authorization" not in calls[0].headers


@pytest.mark.asyncio
async def test_401_with_service_token_retries_once_with_a_fresh_token():
    calls: list = []
    provider = FakeProvider(["tok-A", "tok-B"])

    def responder(request: httpx.Request) -> httpx.Response:
        if request.headers["authorization"] == "Bearer tok-A":
            return httpx.Response(401)
        return httpx.Response(200, json={"query": "q", "results": KNOWLEDGE_RESULTS})

    client = _client(_knowledge(calls, responder), provider)

    assert await client.search("q") == MAPPED
    assert len(calls) == 2
    assert provider.invalidated == ["tok-A"]
    assert calls[1].headers["authorization"] == "Bearer tok-B"


@pytest.mark.asyncio
async def test_401_twice_raises_after_a_single_retry():
    calls: list = []
    provider = FakeProvider(["tok-A", "tok-B"])
    client = _client(_knowledge(calls, lambda r: httpx.Response(401)), provider)

    with pytest.raises(KnowledgeStudioError):
        await client.search("q")

    assert len(calls) == 2


@pytest.mark.asyncio
async def test_401_with_explicit_token_is_not_retried():
    calls: list = []
    provider = FakeProvider(["tok-A"])
    client = _client(_knowledge(calls, lambda r: httpx.Response(401)), provider)

    with pytest.raises(KnowledgeStudioError):
        await client.search("q", auth_token="caller-token")

    assert len(calls) == 1
    assert provider.invalidated == []


@pytest.mark.asyncio
async def test_server_error_raises_knowledge_error():
    client = _client(_knowledge([], lambda r: httpx.Response(500)), FakeProvider(["t"]))

    with pytest.raises(KnowledgeStudioError) as exc_info:
        await client.search("q")

    assert "500" in str(exc_info.value)


@pytest.mark.asyncio
async def test_unreachable_knowledge_raises_knowledge_error():
    def responder(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    client = _client(_knowledge([], responder), FakeProvider(["t"]))

    with pytest.raises(KnowledgeStudioError):
        await client.search("q")


@pytest.mark.asyncio
async def test_non_json_response_raises_knowledge_error():
    client = _client(
        _knowledge([], lambda r: httpx.Response(200, text="<html>")), FakeProvider(["t"])
    )

    with pytest.raises(KnowledgeStudioError):
        await client.search("q")


@pytest.mark.asyncio
async def test_service_token_error_propagates_and_no_request_is_sent():
    calls: list = []
    client = _client(_knowledge(calls, _ok), RaisingProvider())

    with pytest.raises(ServiceTokenError):
        await client.search("q")

    assert calls == []


@pytest.mark.asyncio
async def test_never_calls_the_nonexistent_search_path():
    calls: list = []
    client = _client(_knowledge(calls, _ok), FakeProvider(["t"]))

    await client.search("q")

    assert str(calls[0].url).endswith("/api/v1/knowledge/query")
    assert not str(calls[0].url).endswith("/search")


@pytest.mark.asyncio
async def test_explicit_source_field_wins_over_document_title():
    body = {"results": [{"text": "t", "source": "wiki", "document_title": "Doc", "score": 0.5}]}
    client = _client(_knowledge([], lambda r: httpx.Response(200, json=body)), FakeProvider(["t"]))

    assert await client.search("q") == [{"text": "t", "source": "wiki", "score": 0.5}]


@pytest.mark.asyncio
async def test_missing_fields_get_safe_defaults():
    client = _client(
        _knowledge([], lambda r: httpx.Response(200, json={"results": [{}]})), FakeProvider(["t"])
    )

    assert await client.search("q") == [{"text": "", "source": "unknown", "score": 0.0}]


@pytest.mark.asyncio
async def test_non_object_result_items_raise_knowledge_error():
    client = _client(
        _knowledge([], lambda r: httpx.Response(200, json={"results": ["oops"]})),
        FakeProvider(["t"]),
    )

    with pytest.raises(KnowledgeStudioError):
        await client.search("q")
