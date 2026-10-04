"""
Service token provider — Nova's own identity when it calls other Studios.

Decision 1b = (b), 2026-10-03: Nova calls Knowledge Studio with a service
token that it obtains from the Identity Service (OAuth2 client-credentials
style), not with the caller's forwarded token. This keeps Nova's permission
on Knowledge down to `knowledge:read` and does not couple callers of Nova to
Knowledge's scopes.

Identity Service /token contract (cloudforge-identity-service main.py):
  POST <token_url>, Basic auth (client_id:client_secret),
  JSON body {"scopes": ["knowledge:read"]}
  -> 200 {"access_token": ..., "token_type": "Bearer", "expires_in": 3600,
          "scope": "knowledge:read"}

Nothing here ever logs or puts a secret/token into an exception message.
"""
import asyncio
import logging
import time
from typing import Callable

import httpx

logger = logging.getLogger(__name__)


class ServiceTokenError(Exception):
    """The service token could not be obtained from the Identity Service."""


class ServiceTokenProvider:
    def __init__(
        self,
        token_url: str,
        client_id: str,
        client_secret: str,
        scopes: list[str],
        *,
        timeout: float = 10.0,
        refresh_margin_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._token_url = token_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._scopes = list(scopes)
        self._timeout = timeout
        self._margin = refresh_margin_seconds
        self._clock = clock
        self._transport = transport  # tests inject httpx.MockTransport here
        self._lock = asyncio.Lock()
        self._token: str | None = None
        self._refresh_at = 0.0

    def _is_fresh(self) -> bool:
        return self._token is not None and self._clock() < self._refresh_at

    async def get_token(self) -> str:
        if not self._client_secret:
            raise ServiceTokenError("service credentials are not configured")
        if self._is_fresh():
            return self._token  # type: ignore[return-value]
        async with self._lock:
            # Another waiter may have refreshed while we waited for the lock.
            if not self._is_fresh():
                await self._refresh()
            return self._token  # type: ignore[return-value]

    def invalidate(self, token: str | None = None) -> None:
        """Drop the cached token. When `token` is given, only drop it if it is
        still the cached one, so a late 401 for an old token cannot throw away
        a token another request has just refreshed."""
        if token is None or token == self._token:
            self._token = None
            self._refresh_at = 0.0

    async def _refresh(self) -> None:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                response = await client.post(
                    self._token_url,
                    json={"scopes": self._scopes},
                    auth=httpx.BasicAuth(self._client_id, self._client_secret),
                )
        except (httpx.HTTPError, httpx.InvalidURL) as exc:
            raise ServiceTokenError(
                f"token endpoint unreachable ({type(exc).__name__})"
            ) from None

        if response.status_code != 200:
            raise ServiceTokenError(
                f"token endpoint returned HTTP {response.status_code}"
            )
        try:
            data = response.json()
            token = data["access_token"]
            expires_in = float(data["expires_in"])
        except (ValueError, KeyError, TypeError):
            raise ServiceTokenError("token endpoint returned a malformed response") from None
        if not isinstance(token, str) or not token or expires_in <= 0:
            raise ServiceTokenError("token endpoint returned a malformed response")

        self._token = token
        # Refresh `margin` seconds early; for very short lifetimes refresh at half-life.
        self._refresh_at = self._clock() + max(expires_in - self._margin, expires_in * 0.5)
        logger.info("obtained service token (expires_in=%ss)", int(expires_in))
