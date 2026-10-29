"""导出或恢复已核验的资料总库；不移动原件，不重写历史处理记录。"""
import argparse
import gzip
import hashlib
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / 'database/snapshots/library.sqlite3.gz'
METADATA = SNAPSHOT.with_suffix('.json')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def validate(path):
    with sqlite3.connect(f'{path.resolve().as_uri()}?mode=ro', uri=True) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('资料库完整性核验失败')
        return {table: db.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
                for table in ('downloaded_pdfs', 'pages', 'cleaned_pages', 'processing_runs')}


def export():
    source = ROOT / 'database/sqlite/library.sqlite3'
    summary = json.loads((ROOT / 'reports/library/summary.json').read_text())
    data = source.read_bytes()
    if sha(data) != summary['sqlite_sha256']:
        raise ValueError('总库与已核验报告不一致，请先核验重建')
    for row in json.loads((ROOT / 'reports/library/catalog.json').read_text()):
        if sha((ROOT / row['path']).read_bytes()) != row['sha256']:
            raise ValueError('PDF 原件哈希不匹配')
    counts = validate(source)
    compressed = gzip.compress(data, mtime=0)
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_bytes(compressed)
    METADATA.write_text(json.dumps(dict(format_version=1, database_sha256=sha(data),
        gzip_sha256=sha(compressed), counts=counts, source_report='reports/library/summary.json',
        processing_runs=summary['processing_runs'], scope='只读资料目录；不包含 PDF 文件或模型密钥'), ensure_ascii=False, indent=2))
    return counts


def restore(destination):
    meta = json.loads(METADATA.read_text())
    compressed = SNAPSHOT.read_bytes()
    if sha(compressed) != meta['gzip_sha256']:
        raise ValueError('压缩快照哈希不匹配')
    data = gzip.decompress(compressed)
    if sha(data) != meta['database_sha256']:
        raise ValueError('解压数据库哈希不匹配')
    destination = Path(destination)
    if destination.exists():
        if sha(destination.read_bytes()) == meta['database_sha256']:
            return validate(destination)
        raise ValueError('目标已存在其他数据库，拒绝覆盖')
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix('.restore.sqlite3')
    with temporary.open('xb') as file:
        file.write(data)
    if validate(temporary) != meta['counts']:
        raise ValueError('快照统计不一致')
    temporary.replace(destination)
    return meta['counts']


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['export', 'restore'])
    parser.add_argument('--destination', default=str(ROOT / 'database/sqlite/library.sqlite3'))
    args = parser.parse_args()
    print(json.dumps(export() if args.command == 'export' else restore(args.destination)))
