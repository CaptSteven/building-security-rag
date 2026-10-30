import json
import sqlite3
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from security_rag.api import app
from security_rag.config import Settings
from security_rag import api,library


@pytest.fixture
def local_library(tmp_path,monkeypatch):
    schema=(Path(__file__).resolve().parents[2]/'database/sqlite/library_schema.sql').read_text()
    path=tmp_path/'library.sqlite3'
    pdf=tmp_path/'data/raw/pdfs/run/manual.pdf';pdf.parent.mkdir(parents=True);pdf.write_bytes(b'%PDF-1.4 test fixture')
    with sqlite3.connect(path) as db:
        db.executescript(schema)
        db.execute('INSERT INTO runs VALUES(?,?,?)',('run','manifest.json','manifest-hash'))
        db.execute('INSERT INTO devices VALUES(?,?,?,?,?,?)',('run','dev','AXIS','Test-CAM','视频监控','https://example.com/source'))
        meta=json.dumps({'source_url':'https://example.com/manual.pdf','discovered_on':'https://example.com/source','extraction_status':'completed_unreviewed'})
        db.execute('INSERT INTO assets VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',('run','A1','dev','datasheet','Camera manual','downloaded','data/raw/pdfs/run/manual.pdf','h1',22,1,'https://example.com/manual.pdf',meta))
        db.execute('INSERT INTO assets VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',('run','A2','dev','manual','Outside path','downloaded','secret.pdf','h2',1,1,'https://example.com/other.pdf',meta))
        db.execute('INSERT INTO pages VALUES(?,?,?,?,?)',('run','A1',1,'This camera supports PoE and ONVIF.','h1'))
    cfg=Settings(library_database=path,api_key='test-access')
    monkeypatch.setattr(library,'settings',lambda:cfg)
    monkeypatch.setattr(library,'PROJECT_ROOT',tmp_path)
    monkeypatch.setattr(api,'settings',lambda:cfg)
    with TestClient(app) as client:
        client.headers['X-API-Key']='test-access'
        yield client


def test_library_filters_pagination_and_scope(local_library):
    client=local_library
    assert client.get('/api/library/summary').json()['extracted_pages']==1
    data=client.get('/api/library/documents?extraction=ready&page_size=1').json()
    assert data['total']==1 and data['items'][0]['asset_id']=='A1'
    assert client.get('/api/library/documents?category=门禁').json()['total']==0
    assert client.get('/api/library/documents?q=%25').json()['total']==0
    assert client.get('/api/library/documents?page=0').status_code==422
    assert client.get('/api/library/documents.csv').headers['content-type'].startswith('text/csv')


def test_library_citation_original_file_and_path_boundary(local_library):
    client=local_library
    result=client.post('/api/library/search',json={'question':'PoE'}).json()
    assert result['answer'] is None and result['indexed_pages']==1
    assert result['evidence'][0]['page']==1 and result['evidence'][0]['citation']=='S1'
    assert 'PoE' in result['evidence'][0]['content']
    assert client.get(result['evidence'][0]['file_url']).content.startswith(b'%PDF-')
    assert client.get('/api/library/documents/run/A2/file').status_code==403
    assert client.get('/api/library/documents/run/missing').status_code==404
    assert client.post('/api/library/search',json={'question':'   '}).status_code==422
    client.headers.pop('X-API-Key')
    assert client.get('/api/library/documents/run/A1/file').status_code==401


def test_connections_do_not_disclose_secrets(local_library):
    data=local_library.get('/api/library/connections').json()
    assert data['chat_configured'] is False
    assert 'test-access' not in json.dumps(data)
    assert local_library.get('/api/health').json()['status']=='ok'


def test_cleaned_layer_and_processing_quality_are_separate(local_library):
    from security_rag.library import settings as library_settings
    cfg=library_settings()
    with sqlite3.connect(cfg.library_database) as db:
        db.execute('INSERT INTO processing_runs VALUES(?,?,?,?,?,?,?,?)',('clean-test','test-rule','start','end','manifest','hash',json.dumps({'pages':1}),json.dumps({'version':'test-rule'})))
        db.execute('INSERT INTO cleaned_pages VALUES(?,?,?,?,?,?,?,?,?)',('run','A1',1,'规范化后 PoE','h1','raw-hash','clean-hash','clean-test','["possible_fused_words"]'))
    result=local_library.post('/api/library/search',json={'question':'PoE','text_source':'cleaned'}).json()
    assert result['text_source']=='cleaned' and result['evidence'][0]['content']=='规范化后 PoE'
    assert result['evidence'][0]['quality_flags']==['possible_fused_words']
    raw=local_library.post('/api/library/search',json={'question':'PoE','text_source':'raw'}).json()
    assert raw['evidence'][0]['content']=='This camera supports PoE and ONVIF.'
    summary=local_library.get('/api/library/summary').json()
    assert summary['clean_documents']==1 and summary['quality_flagged_pages']==1
    processing=local_library.get('/api/library/processing').json()
    assert processing['latest']['processing_run_id']=='clean-test'
    assert processing['examples'][0]['page']==1
    assert 'possible_fused_words' in local_library.get('/api/library/processing/quality.csv').text


def test_exact_model_ranks_above_long_generic_page(local_library):
    from security_rag.library import settings
    with sqlite3.connect(settings().library_database) as db:
        db.execute('INSERT INTO devices VALUES(?,?,?,?,?,?)',('run','other','AXIS','Test-CAM-B','视频监控','https://example.com/other'))
        db.execute("UPDATE assets SET device_id='other' WHERE asset_id='A2'")
        db.execute('INSERT INTO pages VALUES(?,?,?,?,?)',('run','A2',1,'Other device PoE. '*300,'h2'))
    result=local_library.post('/api/library/search',json={'question':'Does Test-CAM support PoE?'}).json()
    assert result['evidence'][0]['asset_id']=='A1'
    assert result['evidence'][0]['retrieval_score']>result['evidence'][1]['retrieval_score']
