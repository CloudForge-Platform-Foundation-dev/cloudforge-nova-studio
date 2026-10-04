"""API routes ของ Nova Studio"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status

from src.auth.dependencies import Principal, require_scope
from src.auth.service_token import ServiceTokenError
from src.models.schemas import QueryRequest, QueryResponse
from src.rag.knowledge_client import KnowledgeStudioError
from src.rag.service import RAGService

logger = logging.getLogger(__name__)

router = APIRouter()


def get_rag_service() -> RAGService:
    """
    Dependency provider — override ใน main.py ตอน wiring จริง (ใส่ KnowledgeStudioClient
    และ AnthropicProvider ที่ config มาแล้ว) และ override ใน test ด้วย mock
    """
    raise NotImplementedError("ต้อง override ด้วย dependency_overrides ใน main.py")


@router.post("/query", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    principal: Principal = Depends(require_scope("nova:query")),
    rag_service: RAGService = Depends(get_rag_service),
) -> QueryResponse:
    try:
        return await rag_service.answer(request.question, top_k=request.top_k)
    except ServiceTokenError as exc:
        # Nova's own credentials / the Identity token endpoint, not the caller's fault
        logger.error("cannot obtain service token for Knowledge Studio: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Upstream authentication unavailable",
        ) from None
    except KnowledgeStudioError as exc:
        logger.warning("Knowledge Studio call failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Knowledge Studio request failed",
        ) from None


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}
