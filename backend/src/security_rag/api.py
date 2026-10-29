import secrets
import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from .config import settings
from .db import connect
from .models import Compatibility, Filters, IngestRequest, QueryRequest
from .providers import ProviderError
from .service import KnowledgeBase

app = FastAPI(title="楼宇安保设备知识库", version="0.1.0")


def authorize(x_api_key: str | None = Header(default=None)):
    expected = settings().api_key
    if expected and not secrets.compare_digest(x_api_key or "", expected):
        raise HTTPException(401, "需要有效的 X-API-Key")


@app.exception_handler(ProviderError)
def provider_error(request, exc):
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.exception_handler(psycopg.Error)
def database_error(request, exc):
    return JSONResponse(status_code=503, content={"detail": "数据库操作失败，请检查数据库状态及初始化情况"})


@app.exception_handler(ValueError)
def input_error(request, exc):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/health")
def health():
    with connect(settings()) as conn:
        conn.execute("SELECT 1")
    return {"status": "ok"}


@app.post("/documents", dependencies=[Depends(authorize)])
def ingest(body: IngestRequest):
    return KnowledgeBase(settings()).ingest(body)


@app.post("/query", dependencies=[Depends(authorize)])
def query(body: QueryRequest):
    return KnowledgeBase(settings()).query(body)


@app.post("/devices/search", dependencies=[Depends(authorize)])
def devices(body: Filters):
    from .service import where_clause
    where, args = where_clause(body)
    with connect(settings()) as conn:
        return conn.execute("""SELECT v.id,v.brand,v.model,v.category,d.id AS document_id,
            d.protocols,d.specs,d.source_url,d.version,d.review_status
            FROM devices v JOIN documents d ON v.id=d.device_id WHERE """ + where +
            " ORDER BY v.id,d.id LIMIT 100", args).fetchall()


@app.post("/compatibility", dependencies=[Depends(authorize)])
def add_compatibility(body: Compatibility):
    with connect(settings()) as conn:
        doc = conn.execute("SELECT id FROM documents WHERE id=%s AND review_status='verified' FOR UPDATE",
                           (body.document_id,)).fetchone()
        if not doc:
            raise HTTPException(400, "兼容性声明必须关联已人工核验的资料")
        chunks = conn.execute("SELECT content FROM chunks WHERE document_id=%s ORDER BY ordinal", (body.document_id,)).fetchall()
        if not any(body.evidence_quote in row["content"] for row in chunks):
            raise HTTPException(400, "原文摘录必须完整出现在某个资料片段中")
        return conn.execute("""INSERT INTO compatibility
            (source_device_id,target_device_id,document_id,verdict,conditions,evidence_quote)
            VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT(source_device_id,target_device_id,document_id)
            DO UPDATE SET verdict=EXCLUDED.verdict,conditions=EXCLUDED.conditions,evidence_quote=EXCLUDED.evidence_quote
            RETURNING *""", (body.source_device_id,body.target_device_id,body.document_id,
                               body.verdict,body.conditions,body.evidence_quote)).fetchone()


@app.get("/compatibility/{device_id}", dependencies=[Depends(authorize)])
def compatibility(device_id: int):
    with connect(settings()) as conn:
        rows = conn.execute("""SELECT c.*,d.title,d.source_url,d.version,
            a.brand AS source_brand,a.model AS source_model,b.brand AS target_brand,b.model AS target_model
            FROM compatibility c JOIN documents d ON d.id=c.document_id
            JOIN devices a ON a.id=c.source_device_id JOIN devices b ON b.id=c.target_device_id
            WHERE (c.source_device_id=%s OR c.target_device_id=%s) AND d.review_status='verified'
            ORDER BY c.id LIMIT 100""", (device_id,device_id)).fetchall()
    return {"records": rows, "note": "关系有方向且受条件限制；没有记录表示未知。此接口结果尚未自动注入 /query。"}


# 原始资料目录使用 SQLite，只读访问；不要求 PostgreSQL 启动。
from .library import router as library_router
app.include_router(library_router, dependencies=[Depends(authorize)])


@app.get("/api/health")
def local_health():
    return {"status": "ok", "service": "building-security-rag", "version": "0.2.0"}
