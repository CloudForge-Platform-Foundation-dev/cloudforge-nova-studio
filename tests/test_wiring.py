"""Wiring: main.py ต้องแชร์ token provider ตัวเดียวทั้ง process

_build_rag_service ถูกเรียกทุก request — ถ้าสร้าง provider ในนั้น cache ของ token
จะไม่มีประโยชน์ และ Nova จะขอ token ใหม่จาก Identity Service ทุกครั้ง
"""
from src.main import _build_rag_service, _get_token_provider


def test_every_request_shares_one_service_token_provider(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    first = _build_rag_service()
    second = _build_rag_service()

    shared = _get_token_provider()
    assert first._knowledge_client._token_provider is shared
    assert second._knowledge_client._token_provider is shared
