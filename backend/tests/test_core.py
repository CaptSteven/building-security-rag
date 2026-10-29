import json
import httpx
import pytest
from fastapi.testclient import TestClient
from security_rag.api import app
from security_rag.config import Settings, settings
from security_rag.models import Filters, IngestRequest, QueryRequest
from security_rag.providers import ProviderError, Providers
from security_rag.service import KnowledgeBase, fuse, split_text, where_clause


def test_chunking_preserves_tail_overlap_and_chinese():
    text = "门禁报警资料" * 400
    chunks = split_text(text)
    rebuilt = chunks[0] + "".join(c[150:] for c in chunks[1:])
    assert rebuilt == text
    assert all(len(c) <= 900 for c in chunks)
    assert len(split_text("a" * 900)) == 1
    with pytest.raises(ValueError):
        split_text(text, size=100, overlap=100)


def test_filters_parameterize_untrusted_values_and_require_review():
    malicious = "x' OR TRUE --"
    sql, args = where_clause(Filters(brand=malicious, protocol="ONVIF", spec_equals={"poe": True}))
    assert malicious not in sql and args[0] == malicious
    assert "review_status = 'verified'" in sql
    assert "review_status" not in where_clause(Filters(include_unverified=True))[0]


def test_fusion_deduplicates_and_rewards_dual_retrieval():
    a, b = {"chunk_id": 1}, {"chunk_id": 2}
    rows = fuse([[a, b], [b]], 5)
    assert [row["chunk_id"] for row in rows] == [2, 1]


@pytest.mark.parametrize("vector", [[0, 0], [1], [float("nan"), 1], [True, 1]])
def test_invalid_embedding_rejected(monkeypatch, vector):
    providers = Providers(Settings(embedding_dim=2))
    monkeypatch.setattr(providers, "_post", lambda *args: {"data": [{"index": 0, "embedding": vector}]})
    with pytest.raises(ProviderError):
        providers.embeddings(["安保"])


def test_embedding_response_reordered(monkeypatch):
    providers = Providers(Settings(embedding_dim=2))
    monkeypatch.setattr(providers, "_post", lambda *args: {"data": [
        {"index": 1, "embedding": [0, 1]}, {"index": 0, "embedding": [1, 0]}]})
    assert providers.embeddings(["a", "b"]) == [[1, 0], [0, 1]]


def test_missing_evidence_does_not_call_chat(monkeypatch):
    kb = KnowledgeBase(Settings())
    monkeypatch.setattr(kb, "retrieve", lambda req: [])
    result = kb.query(QueryRequest(question="凭空生成一个型号"))
    assert result["evidence"] == [] and "无法" in result["answer"]


def test_invalid_citation_hidden(monkeypatch):
    kb = KnowledgeBase(Settings())
    monkeypatch.setattr(kb, "retrieve", lambda req: [{"citation": "S1"}])
    monkeypatch.setattr(kb.providers, "answer", lambda *args: "此设备兼容所有门禁 [S99]")
    result = kb.query(QueryRequest(question="兼容吗"))
    assert result["answer"] is None and result["warnings"]


def test_api_auth_and_validation(monkeypatch):
    app.dependency_overrides[settings] = lambda: Settings(api_key="test-key")
    # authorize 直接读取配置，替换其工厂。
    monkeypatch.setattr("security_rag.api.settings", lambda: Settings(api_key="test-key"))
    with TestClient(app) as client:
        assert client.post("/query", json={"question": "门禁"}).status_code == 401
        assert client.post("/query", headers={"X-API-Key": "test-key"}, json={"question": " "}).status_code == 422
    app.dependency_overrides.clear()


def test_demo_is_explicitly_unverified():
    from pathlib import Path
    data = json.loads((Path(__file__).resolve().parents[1] / "examples/demo-camera.json").read_text())
    assert IngestRequest.model_validate(data).review_status == "demo"


def test_provider_http_contract(monkeypatch):
    captured = []
    def handler(request):
        captured.append((request.url.path, request.headers.get("authorization"), json.loads(request.content)))
        if request.url.path.endswith("embeddings"):
            return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1, 0]}]})
        return httpx.Response(200, json={"choices": [{"message": {"content": "依据资料回答 [S1]"}}]})
    original = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: original(transport=httpx.MockTransport(handler), **kw))
    provider = Providers(Settings(embedding_dim=2, embedding_base_url="https://embed.test/v1",
                                 chat_base_url="https://chat.test/v1", chat_api_key="test-only"))
    assert provider.embeddings(["门禁"]) == [[1, 0]]
    assert "[S1]" in provider.answer("协议？", "[]")
    assert captured[0][0] == "/v1/embeddings"
    assert captured[1][0] == "/v1/chat/completions"
    assert captured[1][1] == "Bearer test-only"


def test_api_returns_evidence_without_generation(monkeypatch):
    monkeypatch.setattr("security_rag.api.settings", lambda: Settings(api_key=""))
    monkeypatch.setattr(KnowledgeBase, "retrieve", lambda self, req: [{"citation": "S1", "source_url": "https://example.com/manual"}])
    with TestClient(app) as client:
        response = client.post("/query", json={"question": "门禁", "generate": False, "mode": "relational"})
    assert response.status_code == 200
    assert response.json()["answer"] is None
    assert response.json()["evidence"][0]["citation"] == "S1"
