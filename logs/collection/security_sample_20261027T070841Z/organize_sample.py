"""离线核验与整理；保留初次提取结果，以单独 v2 记录字体依赖修复后的提取。"""
import argparse
import csv
import hashlib
import json
import logging
import shutil
import sqlite3
import subprocess
from datetime import datetime,timezone
from pathlib import Path
from pypdf import PdfReader
from PIL import Image,ImageDraw


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(root):
    data=json.loads((root/'manifest.json').read_text())
    (root/'pages_v2').mkdir(exist_ok=True)
    logging.getLogger('pypdf').addHandler(logging.FileHandler(root/'logs/pdf-extraction-v2.log'))
    report={'checked_at':datetime.now(timezone.utc).isoformat(),'files':[], 'note':'首轮提取曾提示缺少 fontTools；初次 pages/ 保留，本轮使用安装 fontTools 后的 pages_v2/。原件未修改。'}
    conn=sqlite3.connect(root/'catalog.sqlite3')
    covers=[]
    for a in data['assets']:
        if a['status']!='downloaded' or a['kind']=='video':
            continue
        path=root/a['path']
        assert sha(path)==a['sha256'],f"hash mismatch: {path}"
        reader=PdfReader(path)
        assert len(reader.pages)==a['page_count'] and len(reader.pages)>0
        records=[]
        for i,page in enumerate(reader.pages,1):
            text=page.extract_text() or ''
            records.append({'asset_id':a['asset_id'],'raw_sha256':a['sha256'],'page':i,'text':text,
                            'text_sha256':hashlib.sha256(text.encode()).hexdigest(),'extraction_version':'pypdf-with-fonttools-v2'})
        out=root/'pages_v2'/(path.stem+'.jsonl')
        out.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records))
        if 'extraction_history' not in a:
            a['extraction_history']=[{k:a.get(k) for k in ('extracted_path','extracted_sha256','extraction_status')}]
        a.update(extracted_path=str(out.relative_to(root)),extracted_sha256=sha(out),extraction_status='completed_unreviewed')
        for r in records:
            conn.execute('INSERT OR REPLACE INTO pages VALUES(?,?,?,?)',(a['asset_id'],r['page'],r['text'],r['raw_sha256']))
        conn.execute('UPDATE assets SET metadata_json=? WHERE asset_id=?',(json.dumps(a,ensure_ascii=False),a['asset_id']))
        row={'asset_id':a['asset_id'],'raw_sha256_verified':True,'page_count':len(records),
             'extracted_characters':sum(len(r['text']) for r in records),'pages_under_30_chars':[r['page'] for r in records if len(r['text'].strip())<30],
             'text_semantically_reviewed':False,'render_status':'pending'}
        prefix=root/'previews'/path.stem
        try:
            subprocess.run(['pdftoppm','-f','1','-singlefile','-scale-to','600','-png',str(path),str(prefix)],check=True,capture_output=True,timeout=45)
            row['render_status']='first_page_rendered'
            covers.append((a['asset_id']+' '+a['device_id']+' '+a['kind'],prefix.with_suffix('.png')))
        except Exception as exc:
            row['render_status']=str(exc)
        report['files'].append(row)
    report['sqlite_integrity_check']=conn.execute('PRAGMA integrity_check').fetchone()[0]
    assert report['sqlite_integrity_check']=='ok'
    report['devices']=conn.execute('SELECT count(*) FROM devices').fetchone()[0]
    report['pages']=conn.execute('SELECT count(*) FROM pages').fetchone()[0]
    conn.commit();conn.close()
    if covers:
        canvas=Image.new('RGB',(1200,430*((len(covers)+2)//3)), '#dddddd')
        draw=ImageDraw.Draw(canvas)
        for i,(label,path) in enumerate(covers):
            im=Image.open(path).convert('RGB');im.thumbnail((380,390))
            x=(i%3)*400; y=(i//3)*430
            canvas.paste(im,(x+(400-im.width)//2,y))
            draw.text((x+8,y+395),label[:53],fill='black')
        canvas.save(root/'previews/contact-sheet.jpg')
    (root/'manifest.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
    fields=['asset_id','device_id','kind','title','status','path','bytes','sha256','page_count','source_url','discovered_on','retrieved_at','error']
    with (root/'manifest.csv').open('w',newline='',encoding='utf-8-sig') as file:
        writer=csv.DictWriter(file,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(data['assets'])
    (root/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    downloaded=[a for a in data['assets'] if a['status']=='downloaded']
    pending=[a for a in data['assets'] if a['status']!='downloaded']
    lines=['# 楼宇安保设备官方资料小样本','',
           '采集日期：2026-10-27（America/Los_Angeles）。这是本地原始资料库，尚未接入向量数据库或模型。',
           '',f"已下载 {len(downloaded)} 份文件，{len(data['devices'])} 个设备目录，提取 {report['pages']} 页文本；视频已下载数量为 0。",'',
           '## 已下载文件','', '| 编号 | 设备 | 类型 | 页数 | 本地原件 | 官方来源页 |','|---|---|---|---:|---|---|']
    for a in downloaded:
        lines.append(f"| {a['asset_id']} | {a['device_id']} | {a['kind']} | {a['page_count']} | [PDF]({a['path']}) | [来源]({a['discovered_on']}) |")
    lines+=['','## 目录说明','',
            '- raw/：厂商原始 PDF，不改写、不翻译。',
            '- sources/：官方页面快照、采集元数据、robots.txt。初始来源发现发生在采集前，时间见各 JSON；不是站点全量快照。',
            '- pages/：首轮按页提取文本；部分文档出现 fontTools 缺失提示，因此只作历史记录。',
            '- pages_v2/：安装 fontTools 后重新提取的文本。保留页码与原件哈希，未做清洗或语义审核。',
            '- manifest.json / manifest.csv：来源、文件状态、大小、SHA-256、页数、获取时间、提取版本。',
            '- catalog.sqlite3：devices、assets、pages 三张表；assets 中包括失败/待人工记录，查询成功文件须筛选 status。',
            '- logs/：HTTP 状态、工具命令、失败原因和代码/依赖快照。视频没有保存账号或 cookies。',
            '- previews/：每份 PDF 的第一页预览，供检查是否下载到正确文档；不等于逐页人工核验。',
            '', '## 范围与核验边界','',
            'AXIS M2035-LE、A1210、I8116-E；OPTEX FLX-P-DT。选取理由：四类设备各一例，官方来源、小样本可追溯；不是市场代表性抽样。',
            '安装指南可能是系列共用文档；OPTEX 手册还涉及 X5/X8/X9 等变体，不能默认所有子型号参数一致。参数没有自动抽取到 devices 表中。',
            '入侵探测器产品页存在标题型号与概述段型号不完全一致的情况，保留原始页面，不据此自动纠正产品参数。',
            '下载成功只表示文件可读取及哈希一致；未验证全部参数、表格提取顺序或兼容性，也未进行实验评测。',
            '来源均保留厂商版权；未对再分发许可作判断。本轮不把原件发布到公网。',
            '', '## 重现','',
            '在项目根目录执行。每次采集指定新的输出目录，避免覆盖旧证据。',
            '```bash','uv sync --group collection',
            'uv run --group collection python scripts/discover_sources.py > research/catalog/discovery.txt',
            'uv run --group collection python scripts/collect_sample.py --output research/datasets/新的运行目录',
            'uv run --group collection python scripts/organize_sample.py research/datasets/新的运行目录','```',
            '', '```sql',"SELECT d.category,d.brand,d.model,a.kind,a.path FROM assets a JOIN devices d USING(device_id) WHERE a.status='downloaded';",
            "SELECT asset_id,page,substr(text,1,250) FROM pages WHERE text LIKE '%PoE%' LIMIT 10;",'```',
            '', '说明：网页和文件会更新，重现命令用于重新获取和比较；内容一致性应以历史快照及哈希判断，不承诺将来相同 URL 内容不变。',
            '', '待人工项目见 [MANUAL_ACTIONS.md](MANUAL_ACTIONS.md)。']
    (root/'README.md').write_text('\n'.join(lines)+'\n')
    manual=['# 待人工处理','', '这些项目没有下载成功，不计入成功文件数。','']
    for a in pending:
        manual += [f"## {a['asset_id']} · {a['device_id']} · {a['kind']}",'',f"- 原链接：{a['source_url']}",
                   f"- 来源页：{a['discovered_on']}",f"- 原因：{a['error']}",'']
    manual += ['## 交接方法','',
               '视频：在普通浏览器打开上方两个 YouTube 原链接，按平台提示完成登录/人机验证；不向聊天发送密码、cookies 或验证码。完成后告诉我结果，再确认后续可用的获取方式。',
               'OPTEX 手册：可由用户在浏览器手工打开英文手册，下载到本目录 inbox/。其 PDF 路径禁止机器人访问，所以本轮没有自动请求该 PDF。',
               '人工获取后保留原始文件名，并在 inbox/ 中另存文本备注，写明来源 URL、获取时间和手工操作。导入目录数据库前还需计算哈希并登记，不能直接把状态改成 downloaded。']
    (root/'MANUAL_ACTIONS.md').write_text('\n'.join(manual)+'\n')
    (root/'inbox').mkdir(exist_ok=True)
    for name in ['organize_sample.py','discover_sources.py']:
        shutil.copyfile(Path(__file__).with_name(name),root/'logs'/name)
    shutil.copyfile(Path(__file__).resolve().parents[1]/'uv.lock',root/'logs/uv-current.lock')
    with (root/'logs/events.jsonl').open('a') as file:
        file.write(json.dumps({'at':datetime.now(timezone.utc).isoformat(),'event':'offline_organize_and_verify',
                              'script_sha256':sha(Path(__file__)),'manifest_sha256':sha(root/'manifest.json'),
                              'sqlite_sha256':sha(root/'catalog.sqlite3'),'verification_sha256':sha(root/'verification.json')})+'\n')
    print(json.dumps({'downloaded':len(downloaded),'pending':len(pending),'pages':report['pages'],'bytes':sum(a['bytes'] for a in downloaded),'sqlite':report['sqlite_integrity_check']},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path)
    main(parser.parse_args().directory.resolve())
