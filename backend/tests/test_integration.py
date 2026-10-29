"""RAG_TEST_DATABASE_URL 必须指向专用空测试库；不调用任何真实模型 API。"""
import os
import uuid
import pytest
from security_rag.config import Settings
from security_rag.db import assert_space, connect, init_compatibility, init_db
from security_rag.models import Device, Filters, IngestRequest, QueryRequest
from security_rag.service import KnowledgeBase

pytestmark = pytest.mark.integration


def test_postgres_ingest_filter_retrieve_replace(monkeypatch):
    url = os.getenv("RAG_TEST_DATABASE_URL")
    if not url:
        pytest.skip("未配置专用 RAG_TEST_DATABASE_URL")
    cfg = Settings(database_url=url, embedding_base_url="http://test.invalid/v1",
                   embedding_model="integration-only", embedding_dim=3)
    init_db(cfg)
    init_compatibility(cfg)
    kb = KnowledgeBase(cfg)
    monkeypatch.setattr(kb.providers, "embeddings", lambda texts: [[1., 0., 0.] for _ in texts])
    key = "integration:" + str(uuid.uuid4())
    device_id = None
    try:
        req = IngestRequest(source_key=key, title="测试资料", review_status="verified",
            device=Device(brand=key, model="TEST-CAM", category="视频监控", protocols=["ONVIF"], specs={"poe": True}),
            text="TEST-CAM 是虚构测试设备，支持 ONVIF 和 PoE。")
        first = kb.ingest(req)
        kb.ingest(req.model_copy(update={"text": req.text + "更新资料。"}))
        rows = kb.retrieve(QueryRequest(question="TEST-CAM", filters=Filters(brand=key, protocol="ONVIF", spec_equals={"poe": True})))
        assert len(rows) == 1 and rows[0]["document_id"] == first["document_id"]
        assert "更新资料" in rows[0]["content"]
        assert kb.retrieve(QueryRequest(question="TEST-CAM", filters=Filters(brand=key, protocol="不存在"))) == []
        with connect(cfg) as conn:
            device_id = conn.execute("SELECT device_id FROM documents WHERE source_key=%s", (key,)).fetchone()["device_id"]
            with pytest.raises(ValueError):
                assert_space(conn, cfg.model_copy(update={"embedding_model": "different"}))
    finally:
        with connect(cfg) as conn:
            conn.execute("DELETE FROM documents WHERE source_key=%s", (key,))
            if device_id:
                conn.execute("DELETE FROM devices WHERE id=%s", (device_id,))
