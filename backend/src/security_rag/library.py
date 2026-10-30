"""本地资料目录的只读服务。与 PostgreSQL RAG 服务、原始资料分层隔离。"""
import csv
import io
import json
import re
import sqlite3
from typing import Literal
from collections import Counter
from contextlib import contextmanager
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from .config import PROJECT_ROOT, settings
from .providers import Providers

router = APIRouter(prefix='/api/library', tags=['本地资料库'])


@contextmanager
def database():
    path=settings().library_database.resolve()
    if not path.is_file():
        raise HTTPException(503,'资料目录数据库不存在，请先运行 build_library')
    conn=sqlite3.connect(f'{path.as_uri()}?mode=ro',uri=True)
    conn.row_factory=sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def present(row):
    value=dict(row)
    meta=json.loads(value.pop('metadata_json','{}'))
    value.update(source_url=meta.get('source_url',value.get('source_url')),source_page=meta.get('discovered_on',value.get('source_page')),
                 retrieved_at=meta.get('retrieved_at'),extraction_status=meta.get('extraction_status','not_started'),
                 review_status=meta.get('review_status','unreviewed'),cleaning_status=meta.get('cleaning_status','not_started'),
                 cleaning_rules_version=meta.get('cleaning_rules_version'),quality_flagged_pages=meta.get('quality_flagged_pages',0))
    value['file_url']=f"/api/library/documents/{value['run_id']}/{value['asset_id']}/file"
    return value


SELECT="""SELECT a.*,d.brand,d.model,d.category,d.source_page,
    (SELECT count(*) FROM pages p WHERE p.run_id=a.run_id AND p.asset_id=a.asset_id) AS extracted_pages
    FROM assets a JOIN devices d USING(run_id,device_id)"""


def where(q='',category='',brand='',kind='',extraction=''):
    clauses=["a.status='downloaded'", "lower(a.path) LIKE '%.pdf'"];args=[]
    if q.strip():
        # 子串查询保留字面语义，防止 % 和 _ 被用作隐式通配符。
        pattern='%'+q.strip().replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
        clauses.append("(a.title LIKE ? ESCAPE '\\' OR d.model LIKE ? ESCAPE '\\' OR d.brand LIKE ? ESCAPE '\\')")
        args.extend([pattern]*3)
    for field,value in [('d.category',category),('d.brand',brand),('a.kind',kind)]:
        if value:clauses.append(field+'=?');args.append(value)
    if extraction in ['ready','pending']:
        clauses.append(('' if extraction=='ready' else 'NOT ')+"EXISTS(SELECT 1 FROM pages p WHERE p.run_id=a.run_id AND p.asset_id=a.asset_id)")
    return ' AND '.join(clauses),args


@router.get('/summary')
def summary():
    with database() as db:
        rows=db.execute(SELECT+" WHERE a.status='downloaded' AND lower(a.path) LIKE '%.pdf'").fetchall()
        total_text=db.execute('SELECT count(*) FROM pages').fetchone()[0]
        runs=[dict(r) for r in db.execute('SELECT * FROM runs ORDER BY run_id DESC')]
        pending=db.execute("SELECT count(*) FROM assets WHERE status IN ('manual_required','failed')").fetchone()[0]
        has_cleaned=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='cleaned_pages'").fetchone()
        clean_count=clean_pages=flagged_pages=flagged_docs=0
        if has_cleaned:
            clean_count=db.execute("SELECT count(*) FROM (SELECT DISTINCT run_id,asset_id FROM cleaned_pages)").fetchone()[0]
            clean_pages=db.execute('SELECT count(*) FROM cleaned_pages').fetchone()[0]
            flagged_pages=db.execute("SELECT count(*) FROM cleaned_pages WHERE flags_json!='[]'").fetchone()[0]
            flagged_docs=db.execute("SELECT count(*) FROM (SELECT DISTINCT run_id,asset_id FROM cleaned_pages WHERE flags_json!='[]')").fetchone()[0]

    unique={row['sha256']:row for row in rows}
    docs=list(unique.values())
    return dict(documents=len(docs),pdf_pages=sum(r['page_count'] or 0 for r in docs),bytes=sum(r['byte_size'] or 0 for r in docs),
                extracted_documents=sum(bool(r['extracted_pages']) for r in docs),extracted_pages=total_text,
                pending_documents=sum(not r['extracted_pages'] for r in docs),attention=pending,
                categories=dict(Counter(r['category'] for r in docs)),brands=dict(Counter(r['brand'] for r in docs)),
                kinds=dict(Counter(r['kind'] for r in docs)),groups=len({r['device_id'] for r in docs}),runs=runs,
                clean_documents=clean_count,clean_pages=clean_pages,quality_flagged_pages=flagged_pages,quality_flagged_documents=flagged_docs,
                reviewed_documents=sum(json.loads(r["metadata_json"]).get("review_status")=="verified" for r in docs),chunk_documents=0,vector_documents=0)


@router.get('/documents')
def documents(q:str=Query('',max_length=200),category:str='',brand:str='',kind:str='',extraction:str='',
              page:int=Query(1,ge=1),page_size:int=Query(12,ge=1,le=100)):
    clause,args=where(q,category,brand,kind,extraction)
    with database() as db:
        count=db.execute('SELECT count(*) FROM assets a JOIN devices d USING(run_id,device_id) WHERE '+clause,args).fetchone()[0]
        rows=db.execute(SELECT+' WHERE '+clause+' ORDER BY a.run_id DESC,d.category,d.model,a.asset_id LIMIT ? OFFSET ?',
                        [*args,page_size,(page-1)*page_size]).fetchall()
    return dict(items=[present(r) for r in rows],total=count,page=page,page_size=page_size)


@router.get('/documents.csv')
def export_csv():
    with database() as db:
        rows=db.execute(SELECT+" WHERE a.status='downloaded' AND lower(a.path) LIKE '%.pdf' ORDER BY a.run_id,a.asset_id").fetchall()
    stream=io.StringIO();writer=csv.writer(stream)
    writer.writerow(['批次','编号','品牌','产品/系列','设备类别','资料类型','页数','SHA-256','相对路径','官方来源'])
    for r in rows:
        values=[r[k] for k in ['run_id','asset_id','brand','model','category','kind','page_count','sha256','path','source_page']]
        # CSV 在表格软件中打开时避免被厂商文字当作公式。
        writer.writerow(["'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v for v in values])
    return Response('\ufeff'+stream.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="security-library.csv"'})


def get_document(run_id,asset_id):
    with database() as db:
        row=db.execute(SELECT+" WHERE a.run_id=? AND a.asset_id=? AND a.status='downloaded' AND lower(a.path) LIKE '%.pdf'",(run_id,asset_id)).fetchone()
    if not row:raise HTTPException(404,'资料不存在')
    return row


@router.get('/documents/{run_id}/{asset_id}')
def detail(run_id:str,asset_id:str):
    row=get_document(run_id,asset_id)
    with database() as db:
        pages=[dict(p) for p in db.execute('SELECT page,substr(text,1,3000) AS text FROM pages WHERE run_id=? AND asset_id=? ORDER BY page LIMIT 3',(run_id,asset_id))]
    return dict(**present(row),text_preview=pages)


@router.get('/documents/{run_id}/{asset_id}/file')
def pdf_file(run_id:str,asset_id:str):
    row=get_document(run_id,asset_id)
    path=(PROJECT_ROOT/row['path']).resolve()
    if not path.is_relative_to((PROJECT_ROOT/'data/raw/pdfs').resolve()) or path.suffix.lower()!='.pdf':
        raise HTTPException(403,'文件路径不允许访问')
    if not path.is_file():
        if not settings().remote_pdf_enabled:
            raise HTTPException(404,'原件文件缺失')
        from .remote_pdf import fetch_pdf
        data=fetch_pdf(row['source_url'],row['sha256'])
        return Response(data,media_type='application/pdf',headers={
            'X-Content-Type-Options':'nosniff','Cache-Control':'public, max-age=3600'})
    return FileResponse(path,media_type='application/pdf',filename=path.name,content_disposition_type='inline',
                        headers={'X-Content-Type-Options':'nosniff','Cache-Control':'private, no-store'})


class SearchBody(BaseModel):
    question:str=Field(min_length=1,max_length=1000)
    category:str=''
    generate:bool=False
    top_k:int=Field(default=6,ge=1,le=12)
    text_source:Literal["raw","cleaned"]="raw"


@router.post('/search')
def search(body:SearchBody):
    question=body.question.strip()
    if not question:raise HTTPException(422,'请输入有效问题或关键词')
    stopwords={'the','and','does','this','that','with','have','has','can','for','what','which','support','supports','how','its','are','not'}
    terms=list(dict.fromkeys([question,*[word for word in re.findall(r'[A-Za-z0-9][A-Za-z0-9_.-]{1,}',question) if word.lower() not in stopwords]]))[:12]
    condition=' OR '.join('instr(lower(p.text),lower(?))>0' for _ in terms)
    args=list(terms)
    if body.category:condition='('+condition+') AND d.category=?';args.append(body.category)
    table='cleaned_pages' if body.text_source=='cleaned' else 'pages'
    with database() as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone():
            raise HTTPException(409,'该文本层尚未建立，请先使用原始提取文本')
        counts=db.execute('SELECT count(DISTINCT run_id||\':\'||asset_id),count(*) FROM '+table).fetchone()
        # 型号命中优先，其次比较页内命中词数；保留确定性顺序，不声称为语义检索。
        score='+'.join("(CASE WHEN instr(' '||lower(d.model)||' ',' '||lower(?)||' ')>0 THEN 100 WHEN instr(lower(d.model),lower(?))>0 THEN 10 ELSE 0 END + CASE WHEN instr(lower(p.text),lower(?))>0 THEN 1 ELSE 0 END)" for _ in terms)
        score_args=[item for term in terms for item in (term,term,term)]
        rows=db.execute("""SELECT p.page,p.text,a.run_id,a.asset_id,a.title,a.sha256,
            a.metadata_json,d.brand,d.model,d.category, """+("p.flags_json" if body.text_source=="cleaned" else "'[]'")+""" AS flags_json, ("""+score+""") AS retrieval_score FROM """+table+""" p
            JOIN assets a USING(run_id,asset_id) JOIN devices d ON d.run_id=a.run_id AND d.device_id=a.device_id
            WHERE a.status='downloaded' AND ("""+condition+') ORDER BY retrieval_score DESC,length(p.text) DESC,a.run_id,a.asset_id,p.page LIMIT ?',[*score_args,*args,body.top_k*5]).fetchall()
    results=[]
    for row in rows:
        r=dict(row);meta=json.loads(r.pop('metadata_json'));text=r.pop('text');r['quality_flags']=json.loads(r.pop('flags_json'))
        positions=[text.lower().find(term.lower()) for term in terms if term.lower() in text.lower()]
        start=max(0,min(positions,default=0)-160)
        r.update(content=text[start:start+1300],source_url=meta.get('source_url'),source_page=meta.get('discovered_on'),
                 file_url=f"/api/library/documents/{r['run_id']}/{r['asset_id']}/file",citation=f'S{len(results)+1}')
        results.append(r)
        if len(results)>=body.top_k:break
    answer=None;warnings=[]
    if body.generate:
        if not results:answer='现有提取文本中没有找到对应证据，无法据此回答。'
        else:
            answer=Providers(settings()).answer(question,json.dumps(results,ensure_ascii=False))
            cited=set(re.findall(r'\[(S\d+)\]',answer))
            if not cited or not cited<={r['citation'] for r in results}:
                answer=None;warnings.append('模型引用缺失或包含无效编号，回答已隐藏。请检查原文证据。')
    return dict(evidence=results,answer=answer,warnings=warnings,mode='keyword',indexed_documents=counts[0],indexed_pages=counts[1],
                text_source=body.text_source,note='关键词检索。清洗仅规范格式，内容、表格和质量标记仍需核对原始 PDF；未进行切分或向量化。')


@router.get('/connections')
def connections():
    cfg=settings()
    return dict(library='connected',chat_configured=bool(cfg.chat_api_key),chat_model=cfg.chat_model,
                embedding_configured=cfg.embedding_model!='replace-with-your-embedding-model',
                vector_status='not_indexed',authentication_enabled=bool(cfg.api_key),deepseek_byok=True,
                note='配置状态不代表 API 连通性。当前页面检索使用 SQLite 关键词查询；PostgreSQL 向量问答仍由 /query 接口提供。')


@router.get('/attention')
def attention():
    with database() as db:
        rows=db.execute(SELECT+" WHERE a.status IN ('manual_required','failed') ORDER BY a.run_id,a.asset_id").fetchall()
    result=[]
    for row in rows:
        r=present(row)
        meta=json.loads(row['metadata_json']);r['error']=meta.get('error')
        r.pop('file_url',None);result.append(r)
    return {'items':result}


@router.get('/processing')
def processing():
    with database() as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='processing_runs'").fetchone():
            return dict(latest=None,examples=[])
        latest=db.execute('SELECT * FROM processing_runs ORDER BY completed_at DESC LIMIT 1').fetchone()
        if not latest:return dict(latest=None,examples=[])
        rows=db.execute("""SELECT c.run_id,c.asset_id,c.page,c.flags_json,substr(c.text,1,200) AS snippet,
            d.model,d.category FROM cleaned_pages c JOIN assets a USING(run_id,asset_id)
            JOIN devices d ON a.run_id=d.run_id AND a.device_id=d.device_id
            WHERE c.flags_json!='[]' ORDER BY c.run_id,c.asset_id,c.page""").fetchall()
    examples=[];seen=set()
    for flag in ['empty_or_image_page','sparse_text_page','possible_fused_words','fragmented_short_lines','numeric_layout_review','replacement_character','extraction_error']:
        added=0
        for row in rows:
            key=(row['run_id'],row['asset_id'],row['page'])
            if key not in seen and flag in json.loads(row['flags_json']):
                item=dict(row);item['quality_flags']=json.loads(item.pop('flags_json'))
                examples.append(item);seen.add(key);added+=1
                if added>=3:break
    item=dict(latest);item['summary']=json.loads(item.pop('summary_json'));item['rules']=json.loads(item.pop('rules_json'))
    return dict(latest=item,examples=examples)


@router.get('/processing/quality.csv')
def quality_csv():
    with database() as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='cleaned_pages'").fetchone():
            raise HTTPException(409,'尚无清洗核验清单')
        rows=db.execute("""SELECT c.run_id,c.asset_id,d.model,d.category,c.page,c.flags_json FROM cleaned_pages c
            JOIN assets a USING(run_id,asset_id) JOIN devices d ON a.run_id=d.run_id AND a.device_id=d.device_id
            WHERE c.flags_json!='[]' ORDER BY c.run_id,c.asset_id,c.page""").fetchall()
    stream=io.StringIO();writer=csv.writer(stream)
    writer.writerow(['source_run_id','asset_id','model','category','page','quality_flags'])
    for row in rows:
        values=list(row);values[-1]=';'.join(json.loads(values[-1]))
        writer.writerow(["'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v for v in values])
    return Response('\ufeff'+stream.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="quality-review.csv"'})
