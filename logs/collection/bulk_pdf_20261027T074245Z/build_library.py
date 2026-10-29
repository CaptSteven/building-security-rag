"""从各轮 manifest 离线核验并生成总目录；不修改或重新下载原始文件。"""
import argparse
import csv
import json
import os
import sqlite3
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from pypdf import PdfReader
from .layout import ROOT
from .collect_sample import digest


def build(minimum=100):
    report_dir=ROOT/'reports/library'
    report_dir.mkdir(parents=True,exist_ok=True)
    db_path=ROOT/'database/sqlite/library.sqlite3'
    staging=db_path.with_suffix('.staging.sqlite3')
    # 构建独立临时库后原子替换，不在半成品上覆盖已交付总目录。
    if staging.exists():
        raise RuntimeError('存在先前未完成的 staging 数据库，请先检查而不要覆盖')
    connection=sqlite3.connect(staging)
    connection.executescript((ROOT/'database/sqlite/library_schema.sql').read_text())
    files=[];pending=[];unique={};run_info=[]
    for m in sorted((ROOT/'data/metadata/runs').glob('*/manifest.json')):
        data=json.loads(m.read_text())
        if data.get('layout_version')!=2 or data.get('path_base')!='project_root':
            raise ValueError(f'不支持的清单路径格式：{m}')
        run=data['run_id'];devices={d['device_id']:d for d in data['devices']}
        connection.execute('INSERT INTO runs VALUES(?,?,?)',(run,str(m.relative_to(ROOT)),digest(m.read_bytes())))
        run_info.append(dict(run_id=run,manifest=str(m.relative_to(ROOT)),manifest_sha256=digest(m.read_bytes())))
        for d in devices.values():
            connection.execute('INSERT INTO devices VALUES(?,?,?,?,?,?)',(run,*[d[k] for k in ['device_id','brand','model','category','source_page']]))
        for a in data['assets']:
            connection.execute('INSERT INTO assets VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
              (run,a['asset_id'],a['device_id'],a['kind'],a['title'],a['status'],a.get('path'),a.get('sha256'),a.get('bytes'),a.get('page_count'),a['source_url'],json.dumps(a,ensure_ascii=False)))
            if a['status']=='downloaded' and a.get('path','').endswith('.pdf'):
                path=ROOT/a['path']
                if not path.resolve().is_relative_to(ROOT/'data/raw/pdfs'):
                    raise ValueError('原始 PDF 不在规范目录')
                actual=digest(path.read_bytes())
                assert actual==a['sha256'],f'文件哈希不匹配 {path}'
                pages=len(PdfReader(path).pages)
                assert pages==a['page_count'] and pages>0
                d=devices[a['device_id']]
                row=dict(run_id=run,asset_id=a['asset_id'],brand=d['brand'],model=d['model'],category=d['category'],
                         kind=a['kind'],title=a['title'],path=a['path'],sha256=actual,bytes=path.stat().st_size,
                         page_count=pages,source_url=a['source_url'],source_page=a['discovered_on'],
                         retrieved_at=a.get('retrieved_at'),extraction_status=a.get('extraction_status','unknown'))
                files.append(row)
                unique.setdefault(actual,row)
                if a.get('extracted_path'):
                    extracted=ROOT/a['extracted_path']
                    assert digest(extracted.read_bytes())==a['extracted_sha256']
                    for line in extracted.read_text().splitlines():
                        page=json.loads(line)
                        assert page['raw_sha256']==actual
                        connection.execute('INSERT INTO pages VALUES(?,?,?,?,?)',(run,a['asset_id'],page['page'],page['text'],actual))
            elif a['status'] in ['manual_required','failed']:
                pending.append(dict(run_id=run,**a))
    unique_files=list(unique.values())
    connection.commit()
    assert connection.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert not connection.execute('PRAGMA foreign_key_check').fetchall()
    indexed_pages=connection.execute('SELECT count(*) FROM pages').fetchone()[0]
    assert len(unique)>=minimum,f'仅有 {len(unique)} 份不同 PDF，未达到目标 {minimum}'
    connection.close()
    staging.replace(db_path)
    summary=dict(verified_at=datetime.now(timezone.utc).isoformat(),unique_readable_pdfs=len(unique),physical_pdf_files=len(files),
                 duplicate_content_files=len(files)-len(unique),pdf_pages=sum(r['page_count'] for r in unique_files),
                 bytes=sum(r['bytes'] for r in unique_files),by_category=dict(Counter(r['category'] for r in unique_files)),
                 by_brand=dict(Counter(r['brand'] for r in unique_files)),by_document_type=dict(Counter(r['kind'] for r in unique_files)),
                 indexed_text_pages=indexed_pages,manual_or_failed=len(pending),runs=run_info,
                 sqlite_integrity='ok',sqlite_sha256=digest(db_path.read_bytes()),
                 scope='官方设备资料小样本，含历史产品与系列共用文档；不代表市场占有率抽样。')
    (report_dir/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    (report_dir/'catalog.json').write_text(json.dumps(unique_files,ensure_ascii=False,indent=2))
    columns=list(unique_files[0])
    with (report_dir/'catalog.csv').open('w',newline='',encoding='utf-8-sig') as file:
        w=csv.DictWriter(file,fieldnames=columns);w.writeheader();w.writerows(unique_files)
    def link(path):return Path(os.path.relpath(ROOT/path,report_dir)).as_posix()
    lines=['# 安保设备官方 PDF 总目录','',
           f"核验结果：**{len(unique)} 份内容不同且可读取的官方 PDF，共 {summary['pdf_pages']} 页，约 {summary['bytes']/1_000_000:.1f} MB。**",'',
           '统计按原始文件 SHA-256 去重，不按网址、页数或片段数量计数。原件没有清洗、切分或翻译；新增批次尚未提取文本。',
           '',f"[SQLite 总目录]({link('database/sqlite/library.sqlite3')}) · [CSV 文件清单](catalog.csv) · [完整 JSON](catalog.json) · [统计与哈希核验](summary.json)",
           '', '## 类别分布','', '| 类别 | PDF 数 |','|---|---:|']
    for category,count in summary['by_category'].items():lines.append(f'| {category} | {count} |')
    lines+=['','## 文档类型','', '| 类型 | PDF 数 |','|---|---:|']
    for kind,count in summary['by_document_type'].items():lines.append(f'| {kind} | {count} |')
    lines+=['','## 原始文件','', '| 编号 | 品牌 / 产品或系列 | 类别 | 类型 | 页数 | 本地文件 | 来源 |','|---|---|---|---|---:|---|---|']
    for r in unique_files:
        model=r['model'].replace('|','/')
        lines.append(f"| {r['run_id']} / {r['asset_id']} | {r['brand']} {model} | {r['category']} | {r['kind']} | {r['page_count']} | [PDF]({link(r['path'])}) | [官方页]({r['source_page']}) |")
    lines+=['','## 使用边界','',
            '所有原件位于 data/raw/pdfs/<run_id>/<category>/<device_id>/；来源页面和 robots 快照归 data/raw/webpages/，清单归 data/metadata/，过程日志归 logs/collection/。',
            '资料数量不是型号数量。系列手册可能覆盖多个型号，产品目录标签仍需人工核验。当前库不自动纠正厂商内容，不推断兼容性，不把历史设备称为在售设备。',
            f'当前 SQLite 文本索引包含此前小样本的 {indexed_pages} 页；其余 PDF 只登记原件和页数，不表示已完成提取或入向量库。',
            '文档版权保留厂商原样，本轮没有将下载原件发布到公网。',
            '', '## 离线复核','', '```bash','uv run --group collection python -m pipelines.collection.build_library --minimum 100','```',
            '', '```sql','SELECT category,count(DISTINCT sha256) FROM downloaded_pdfs GROUP BY category;',
            'SELECT run_id,asset_id,model,kind,path FROM downloaded_pdfs LIMIT 20;','```']
    (report_dir/'README.md').write_text('\n'.join(lines)+'\n')
    (report_dir/'manual-actions.json').write_text(json.dumps(pending,ensure_ascii=False,indent=2))
    manual=['# 需人工处理或未成功下载的资料','', '这些条目不计入已下载 PDF 数量。历史小样本中的两个视频在本轮没有重新尝试。','']
    for a in pending:
        manual += [f"## {a['run_id']} / {a['asset_id']}",'',f"- 标题：{a['title']}",
                   f"- [资源原链接]({a['source_url']})",f"- [来源页]({a['discovered_on']})",f"- 原因：{a.get('error','未记录')}",'']
    (report_dir/'MANUAL_ACTIONS.md').write_text('\n'.join(manual)+'\n')

    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--minimum',type=int,default=100)
    build(p.parse_args().minimum)
