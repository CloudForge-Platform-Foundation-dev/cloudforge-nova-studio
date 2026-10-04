"""Nova Studio — FastAPI entrypoint"""
import functools
import os

from fastapi import FastAPI

from src.api.routes import get_rag_service, router
from src.auth.config import auth_settings, service_credentials
from src.auth.service_token import ServiceTokenProvider
from src.llm.anthropic_provider import AnthropicProvider
from src.rag.knowledge_client import KnowledgeStudioClient
from src.rag.service import RAGService

app = FastAPI(title="CloudForge Nova Studio", version="0.2.0")
app.include_router(router)


@functools.lru_cache(maxsize=1)
def _get_token_provider() -> ServiceTokenProvider:
    """One provider for the whole process. _build_rag_service below runs on
    every request, so the token cache must live outside it or Nova would ask
    the Identity Service for a new token on every call."""
    return ServiceTokenProvider(
        token_url=auth_settings.token_url,
        client_id=service_credentials.client_id,
        client_secret=service_credentials.client_secret,
        scopes=["knowledge:read"],
    )


def _build_rag_service() -> RAGService:
    knowledge_client = KnowledgeStudioClient(
        base_url=os.environ.get("KNOWLEDGE_STUDIO_URL", "http://localhost:8001"),
        token_provider=_get_token_provider(),
    )
    llm_provider = AnthropicProvider(api_key=os.environ["ANTHROPIC_API_KEY"])
    return RAGService(knowledge_client=knowledge_client, llm_provider=llm_provider)


app.dependency_overrides[get_rag_service] = _build_rag_service
