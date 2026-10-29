import hashlib
import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from security_rag.deployed_app import create_app
from security_rag import remote_pdf
from pipelines.deployment.snapshot import restore, validate, ROOT


def test_snapshot_restore_and_refuse_overwrite(tmp_path):
    destination = tmp_path / 'library.sqlite3'
    assert restore(destination)['pages'] == 1888
    assert restore(destination) == validate(destination)
    destination.write_bytes(b'other database')
    with pytest.raises(ValueError, match='拒绝覆盖'):
        restore(destination)


def test_public_entry_has_no_write_routes_and_blocks_paid_generation(tmp_path):
    (tmp_path / 'index.html').write_text('<h1>Sentinel</h1>')
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/').status_code == 200
        assert client.post('/documents', json={}).status_code in (404, 405)
        assert client.post('/compatibility', json={}).status_code in (404, 405)
        assert client.post('/api/library/search', json={'question':'PoE','generate':True}).status_code == 403


def test_remote_pdf_checks_hash_and_redirect_host(monkeypatch):
    payload = b'%PDF-1.4 verified fixture'
    seen = []
    def transport(request):
        seen.append(request.url.host)
        if request.url.path == '/redirect':
            return httpx.Response(302, headers={'location':'https://127.0.0.1/secret'})
        return httpx.Response(200, content=payload)
    client_class = httpx.Client
    monkeypatch.setattr(remote_pdf.httpx, 'Client', lambda **kw: client_class(transport=httpx.MockTransport(transport), **kw))
    remote_pdf._cache.clear()
    digest = hashlib.sha256(payload).hexdigest()
    assert remote_pdf.fetch_pdf('https://www.axis.com/manual.pdf', digest) == payload
    with pytest.raises(HTTPException) as error:
        remote_pdf.fetch_pdf('https://www.axis.com/manual.pdf', 'wrong')
    assert error.value.status_code == 502
    with pytest.raises(HTTPException):
        remote_pdf.fetch_pdf('https://www.axis.com/redirect', 'redirect')
    assert seen == ['www.axis.com', 'www.axis.com', 'www.axis.com']
    with pytest.raises(HTTPException):
        remote_pdf.check_url('https://www.axis.com@127.0.0.1/manual.pdf')
