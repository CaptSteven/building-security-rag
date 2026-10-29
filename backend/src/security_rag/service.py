import hashlib
import json
import re
from psycopg.types.json import Jsonb
from .config import Settings
from .db import assert_space, connect
from .models import Filters, IngestRequest, QueryRequest
from .providers import Providers


def split_text(text: str, size: int = 900, overlap: int = 150) -> list[str]:
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError("invalid chunk settings")
    text = text.strip()
    result = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        result.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return result


def vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(str(x) for x in vector) + "]"


def where_clause(filters: Filters) -> tuple[str, list]:
    clauses, args = [], []
    for field in ("brand", "model", "category"):
        value = getattr(filters, field)
        if value is not None:
            clauses.append(f"v.{field} = %s")
            args.append(value)
    if filters.protocol is not None:
        clauses.append("d.protocols @> %s")
        args.append(Jsonb([filters.protocol]))
    if filters.spec_equals:
        clauses.append("d.specs @> %s")
        args.append(Jsonb(filters.spec_equals))
    if not filters.include_unverified:
        clauses.append("d.review_status = 'verified'")
    return " AND ".join(clauses) or "TRUE", args


def fuse(rankings: list[list[dict]], limit: int) -> list[dict]:
    by_id, scores = {}, {}
    for ranking in rankings:
        for rank, row in enumerate(ranking, 1):
            key = row["chunk_id"]
            by_id[key] = row
            scores[key] = scores.get(key, 0) + 1 / (60 + rank)
    keys = sorted(scores, key=lambda key: (-scores[key], key))[:limit]
    return [dict(by_id[key], fusion_score=scores[key]) for key in keys]


class KnowledgeBase:
    def __init__(self, config: Settings):
        self.config = config
        self.providers = Providers(config)

    def ingest(self, request: IngestRequest) -> dict:
        pieces = split_text(request.text)
        vectors = []
        for offset in range(0, len(pieces), 32):
            vectors.extend(self.providers.embeddings(pieces[offset:offset + 32]))
        fingerprint = hashlib.sha256(request.text.encode()).hexdigest()
        with connect(self.config) as conn:
            assert_space(conn, self.config)
            # 同品牌同型号分类应一致；避免入库顺序悄悄改变旧资料类别。
            device = conn.execute("""INSERT INTO devices (brand, model, category)
                VALUES (%s,%s,%s) ON CONFLICT (brand,model) DO UPDATE SET brand=EXCLUDED.brand
                RETURNING id, category""", (request.device.brand, request.device.model, request.device.category)).fetchone()
            if device["category"] != request.device.category:
                raise ValueError("同品牌同型号的设备类别冲突")
            doc = conn.execute("""INSERT INTO documents
                (source_key,title,source_url,version,published_on,device_id,protocols,specs,review_status,content_hash)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (source_key) DO UPDATE SET title=EXCLUDED.title, source_url=EXCLUDED.source_url,
                version=EXCLUDED.version,published_on=EXCLUDED.published_on,device_id=EXCLUDED.device_id,
                protocols=EXCLUDED.protocols,specs=EXCLUDED.specs,review_status=EXCLUDED.review_status,
                content_hash=EXCLUDED.content_hash,ingested_at=now() RETURNING id""",
                (request.source_key, request.title, str(request.source_url) if request.source_url else None,
                 request.version, request.published_on, device["id"], Jsonb(request.device.protocols),
                 Jsonb(request.device.specs), request.review_status, fingerprint)).fetchone()
            conn.execute("DELETE FROM compatibility WHERE document_id=%s", (doc["id"],))
            conn.execute("DELETE FROM chunks WHERE document_id=%s", (doc["id"],))
            for ordinal, (piece, vector) in enumerate(zip(pieces, vectors, strict=True)):
                conn.execute("""INSERT INTO chunks (document_id,ordinal,page,content,embedding)
                    VALUES (%s,%s,%s,%s,%s::vector)""", (doc["id"], ordinal, request.page, piece, vector_literal(vector)))
        return {"document_id": doc["id"], "chunks": len(pieces), "content_hash": fingerprint}

    def retrieve(self, request: QueryRequest) -> list[dict]:
        where, params = where_clause(request.filters)
        select = """SELECT c.id AS chunk_id,c.content,c.page,d.id AS document_id,d.title,
            d.source_url,d.version,d.published_on,d.review_status,d.protocols,d.specs,
            v.brand,v.model,v.category
            FROM chunks c JOIN documents d ON d.id=c.document_id
            JOIN devices v ON v.id=d.device_id"""
        rankings = []
        vector = None
        if request.mode != "relational":
            vector = vector_literal(self.providers.embeddings([request.question])[0])
        with connect(self.config) as conn:
            assert_space(conn, self.config)
            # MVP 用过滤后的精确向量搜索，确保严格筛选不因 ANN 候选不足而漏召回。
            # 数据量大后再评估 iterative HNSW 扫描和 recall@k。
            if vector is not None:
                rows = conn.execute(select + f" WHERE {where} ORDER BY (c.embedding <=> %s::vector) + 0, c.id LIMIT %s",
                                    [*params, vector, request.top_k * 4]).fetchall()
                rankings.append(rows)
            if request.mode != "vector":
                # 完整型号优先；中文连续文本支持子串匹配，不冒充中文 BM25。
                terms = list(dict.fromkeys([request.question.strip(), *re.findall(r"[A-Za-z0-9][A-Za-z0-9_.-]*", request.question)]))[:16]
                match = " OR ".join("strpos(lower(c.content || ' ' || v.model || ' ' || v.brand),lower(%s)) > 0" for _ in terms)
                rows = conn.execute(select + f" WHERE {where} AND ({match}) ORDER BY c.id LIMIT %s",
                                    [*params, *terms, request.top_k * 4]).fetchall()
                rankings.append(rows)
                # 显式筛选是结构化意图，即使文档未出现问题原句也返回符合条件的资料。
                if request.filters.model_dump(exclude_defaults=True, exclude={"include_unverified"}):
                    rankings.append(conn.execute(select + f" WHERE {where} ORDER BY c.id LIMIT %s",
                                                 [*params, request.top_k * 4]).fetchall())
        return [dict(row, citation=f"S{i}") for i, row in enumerate(fuse(rankings, request.top_k), 1)]

    def query(self, request: QueryRequest) -> dict:
        evidence = self.retrieve(request)
        answer = None
        warnings = []
        if request.generate:
            if not evidence:
                answer = "当前知识库没有找到符合条件的证据，无法据此回答。"
            else:
                answer = self.providers.answer(request.question, json.dumps(evidence, ensure_ascii=False, default=str))
                cited = set(re.findall(r"\[(S\d+)\]", answer))
                valid = {row["citation"] for row in evidence}
                if not cited or not cited <= valid:
                    warnings.append("模型引用缺失或包含无效编号，回答已隐藏，请查阅原始证据。")
                    answer = None
        return {"answer": answer, "evidence": evidence, "warnings": warnings, "mode": request.mode}
