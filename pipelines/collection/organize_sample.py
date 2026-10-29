from pipelines.jsonl import read_jsonl
"""离线核验分类后的资料库并生成报告；不修改原件，不清洗，不切分。"""
import argparse
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from pypdf import PdfReader
from .layout import ROOT, DatasetLayout


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(run_id):
    layout = DatasetLayout(run_id)
    manifest = json.loads((layout.metadata / 'manifest.json').read_text())
    if manifest.get('layout_version') != 2 or manifest.get('path_base') != 'project_root':
        raise ValueError('需要 layout_version=2、以项目根目录为路径基准的清单')
    checks=[]
    for asset in manifest['assets']:
        if asset['status'] != 'downloaded':
            continue
        file=ROOT / asset['path']
        assert file.resolve().is_relative_to(ROOT)
        assert sha(file)==asset['sha256'],f'原件哈希不匹配：{file}'
        if asset['kind'] != 'video':
            assert file.is_relative_to(layout.pdfs)
            assert len(PdfReader(file).pages)==asset['page_count']
        if asset.get('extracted_path'):
            assert sha(ROOT / asset['extracted_path'])==asset['extracted_sha256']
            for row in read_jsonl(ROOT / asset['extracted_path']):
                assert row['raw_sha256']==asset['sha256']
                assert hashlib.sha256(row['text'].encode()).hexdigest()==row['text_sha256']
        checks.append({'asset_id':asset['asset_id'],'sha256_verified':True,'path':asset['path']})
    with sqlite3.connect(f'file:{layout.database}?mode=ro',uri=True) as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        for a in manifest['assets']:
            row=db.execute('SELECT path,metadata_json FROM assets WHERE asset_id=?',(a['asset_id'],)).fetchone()
            assert row and row[0]==a.get('path')
            assert json.loads(row[1])==a
        pages=db.execute('SELECT count(*) FROM pages').fetchone()[0]
    downloaded=[a for a in manifest['assets'] if a['status']=='downloaded']
    pending=[a for a in manifest['assets'] if a['status']!='downloaded']
    layout.reports.mkdir(parents=True,exist_ok=True)
    def link(path):
        return Path(os.path.relpath(path,layout.reports)).as_posix()
    lines=['# 官方资料小型数据库','',
           f'运行编号：`{run_id}`。目录规范版本：2。',
           f'已下载 {len(downloaded)} 份文件，包含 {len(manifest["devices"])} 个设备目录，共 {pages} 页提取文本。待人工项目 {len(pending)} 个。','',
           '## 已下载资料','', '| 编号 | 设备 | 类型 | 页数 | 原始文件 |','|---|---|---|---:|---|']
    for a in downloaded:
        lines.append(f'| {a["asset_id"]} | {a["device_id"]} | {a["kind"]} | {a.get("page_count", "—")} | [原件]({link(ROOT/a["path"])}) |')
    lines += ['', '## 数据分层','',
              f'- [原始 PDF 文件夹]({link(layout.pdfs)}/)：下载原件，清洗及切分前的文件独立存放。',
              f'- [原始视频目录]({link(layout.videos)}/)：目前无成功下载的视频。',
              f'- [SQLite 资料目录数据库]({link(layout.database)})：设备、文件状态、逐页提取文本。',
              f'- [完整清单 JSON]({link(layout.metadata/"manifest.json")}) / [CSV]({link(layout.metadata/"manifest.csv")})：所有文件路径以项目根目录为基准。',
              f'- [来源快照]({link(layout.sources)}/) 与 [原始日志]({link(layout.logs)}/)。',
              f'- [第一页预览]({link(layout.previews/"contact-sheet.jpg")})：已核对封面；不代表逐页语义审核。',
              '', '## 尚未完成的内容','',
              '文本仅按页提取，未清洗、未切分、未向量化；数据条目没有被标为人工核验通过。v1 是首轮历史提取，v2 是补充 fontTools 后的重新提取；两版都属于未清洗文本。',
              '文件中可能含多个语言、多个系列型号或硬件变体，不能按 en-US 文件名推定全篇语言或参数适用范围。',
              '本目录下的 verification.json 是采集时历史核验记录；layout-verification.json 是目录迁移后的路径、哈希与数据库一致性核验。',
              '', '## 待人工处理','',
              '2 条 YouTube 官方视频要求登录/确认不是机器人；1 份 OPTEX 手册的 PDF 路径禁止机器人自动获取。本轮均未下载。',
              '[人工操作清单](MANUAL_ACTIONS.md)。来源厂商版权保持原样，未公开发布原文件。',
              '', '## 离线核验','', '在项目根目录执行：','```bash',
              f'uv run --group collection python -m pipelines.collection.organize_sample --run-id {run_id}','```']
    (layout.reports/'README.md').write_text('\n'.join(lines)+'\n')
    lines=['# 待人工处理','', '以下文件未下载成功，不能计入已有语料。','']
    for a in pending:
        lines += [f'## {a["asset_id"]} · {a["device_id"]} · {a["kind"]}','',
                  f'- [文件/视频原链接]({a["source_url"]})',f'- [官方来源页]({a["discovered_on"]})',f'- 原因：{a["error"]}','']
    lines += [f'人工取得文件后放入 `{layout.relative(layout.inbox)}/`，保留原始文件名，另记来源 URL、下载时间和操作方式，重新登记哈希后再导入目录数据库。不要直接覆盖原始 PDF 或修改 downloaded 状态。',
              '如需登录，请在普通浏览器完成；不向聊天发送密码、cookies 或验证码。']
    (layout.reports/'MANUAL_ACTIONS.md').write_text('\n'.join(lines)+'\n')
    report={'at':datetime.now(timezone.utc).isoformat(),'layout_version':2,'files':checks,'sqlite_integrity_check':'ok',
            'sqlite_pages':pages,'manifest_sha256':sha(layout.metadata/'manifest.json'),'database_sha256':sha(layout.database)}
    (layout.reports/'layout-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({'verified_files':len(checks),'sqlite_pages':pages,'pending':len(pending)},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run-id',required=True)
    main(parser.parse_args().run_id)
