import io
import json
import sqlite3
from pathlib import Path
import pytest
pytest.importorskip('bs4',reason='collection group not installed')
from pypdf import PdfWriter
from pipelines.collection import build_library
from pipelines.collection.collect_sample import digest


def test_build_library_checks_pdf_and_merges_run_identity(tmp_path,monkeypatch):
    writer=PdfWriter();writer.add_blank_page(width=100,height=100)
    stream=io.BytesIO();writer.write(stream);body=stream.getvalue()
    schema=Path(build_library.ROOT/'database/sqlite/library_schema.sql').read_text()
    (tmp_path/'database/sqlite').mkdir(parents=True)
    (tmp_path/'database/sqlite/library_schema.sql').write_text(schema)
    path=tmp_path/'data/raw/pdfs/test/a.pdf';path.parent.mkdir(parents=True);path.write_bytes(body)
    folder=tmp_path/'data/metadata/runs/test';folder.mkdir(parents=True)
    data={'layout_version':2,'path_base':'project_root','run_id':'test',
          'devices':[{'device_id':'test','brand':'TEST','model':'fixture','category':'视频监控','source_page':'https://example.com/fixture'}],
          'assets':[{'asset_id':'A1','device_id':'test','kind':'datasheet','title':'test fixture','status':'downloaded',
                     'path':str(path.relative_to(tmp_path)),'sha256':digest(body),'bytes':len(body),'page_count':1,
                     'source_url':'https://example.com/fixture.pdf','discovered_on':'https://example.com/fixture'}]}
    (folder/'manifest.json').write_text(json.dumps(data))
    monkeypatch.setattr(build_library,'ROOT',tmp_path)
    build_library.build(minimum=1)
    with sqlite3.connect(tmp_path/'database/sqlite/library.sqlite3') as db:
        assert db.execute('SELECT model,page_count FROM downloaded_pdfs').fetchone()==('fixture',1)
        assert db.execute('PRAGMA foreign_key_check').fetchall()==[]
    summary=json.loads((tmp_path/'reports/library/summary.json').read_text())
    assert summary['unique_readable_pdfs']==1 and summary['indexed_text_pages']==0
