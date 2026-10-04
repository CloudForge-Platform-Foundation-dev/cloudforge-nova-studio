"""Client สำหรับเรียก semantic search ของ Knowledge Studio (studio ตัวที่ 2)"""
import logging
from typing import Protocol

import httpx

logger = logging.getLogger(__name__)


class KnowledgeStudioError(Exception):
    """Knowledge Studio could not be reached or returned an error response."""


class TokenProvider(Protocol):
    async def get_token(self) -> str: ...

    def invalidate(self, token: str | None = None) -> None: ...


class KnowledgeStudioClient:
    def __init__(
        self,
        base_url: str,
        timeout: float = 10.0,
        *,
        token_provider: TokenProvider | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._token_provider = token_provider
        self._transport = transport  # tests inject httpx.MockTransport here

    async def search(
        self, query: str, *, top_k: int = 5, auth_token: str | None = None
    ) -> list[dict]:
        """
        เรียก endpoint search ของ Knowledge Studio

        คืนค่าเป็น list ของ dict รูปแบบ {"text": str, "source": str, "score": float}
        NOTE: path/response shape ตรงนี้อ้างอิงตาม API ที่ตกลงกันไว้ — ถ้า Knowledge Studio
        เปลี่ยน contract ต้องอัปเดตที่นี่ด้วย

        Auth (decision 1b = b): ถ้าไม่ส่ง `auth_token` มา จะใช้ service token ของ Nova
        จาก `token_provider` (scope knowledge:read) — ไม่ forward token ของผู้เรียก
        `auth_token` ที่ส่งมาตรง ๆ ยังใช้ได้และมาก่อนเสมอ
        Raises ServiceTokenError (ขอ token ไม่ได้) หรือ KnowledgeStudioError
        """
        use_provider = auth_token is None and self._token_provider is not None
        token = auth_token
        if use_provider:
            token = await self._token_provider.get_token()

        response = await self._post_search(query, top_k, token)

        if response.status_code == 401 and use_provider:
            # The cached service token may be stale (e.g. Identity rotated its
            # signing key). Drop exactly that token and retry once with a new one.
            self._token_provider.invalidate(token)
            token = await self._token_provider.get_token()
            response = await self._post_search(query, top_k, token)

        if not response.is_success:
            raise KnowledgeStudioError(
                f"Knowledge Studio returned HTTP {response.status_code}"
            )
        try:
            return response.json().get("results", [])
        except (ValueError, AttributeError):
            raise KnowledgeStudioError("Knowledge Studio returned a malformed response") from None

    async def _post_search(
        self, query: str, top_k: int, token: str | None
    ) -> httpx.Response:
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                return await client.post(
                    f"{self._base_url}/search",
                    json={"query": query, "top_k": top_k},
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            raise KnowledgeStudioError(
                f"Knowledge Studio unreachable ({type(exc).__name__})"
            ) from None
