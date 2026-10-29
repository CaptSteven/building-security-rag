"""全库提取和保守清洗。run 生成新产物；publish 经核验后更新当前目录。"""
import argparse
import csv
import json
import logging
import shutil
import sqlite3
import sys
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from pypdf import PdfReader
from pipelines.collection.layout import ROOT,DatasetLayout
from pipelines.collection.collect_sample import digest
from .rules import VERSION,RULES,clean_page,quality_flags,text_hash


def now():return datetime.now(timezone.utc).isoformat()


def locations(run_id):
    DatasetLayout(run_id)  # 复用 run_id 路径安全校验。
    return dict(metadata=ROOT/'data/metadata/processing'/run_id,
                extracted=ROOT/'data/interim/extracted'/run_id/'v1',
                cleaned=ROOT/'data/processed/cleaned'/run_id,
                logs=ROOT/'logs/processing'/run_id,
                reports=ROOT/'reports/processing'/run_id)


def json_write(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2))


def log(paths,event,**data):
    with (paths['logs']/'events.jsonl').open('a') as file:
        file.write(json.dumps(dict(at=now(),event=event,**data),ensure_ascii=False)+'\n')


def run(run_id):
    paths=locations(run_id)
    paths['metadata'].mkdir(parents=True,exist_ok=False)
    for key,path in paths.items():
        if key!='metadata':path.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(__file__,paths['logs']/'process_library.py')
    shutil.copyfile(Path(__file__).with_name('rules.py'),paths['logs']/'rules.py')
    shutil.copyfile(ROOT/'uv.lock',paths['logs']/'uv.lock')
    logging.getLogger('pypdf').addHandler(logging.FileHandler(paths['logs']/'pypdf.log'))
    sources=[]
    for path in sorted((ROOT/'data/metadata/runs').glob('*/manifest.json')):
        data=json.loads(path.read_text());devices={d['device_id']:d for d in data['devices']}
        for a in data['assets']:
            if a['status']=='downloaded' and a.get('path','').endswith('.pdf'):
                sources.append(dict(a,source_run_id=data['run_id'],device=devices[a['device_id']]))
    json_write(paths['metadata']/'inputs.json',sources)
    json_write(paths['metadata']/'rules.json',dict(version=VERSION,rules=RULES,
        forbidden=['不补写事实','不改写数字、型号或单位','不自动拼词/去连字符','不移除页眉页脚','不丢弃空页','不做OCR或模型改写'],offset_unit='Python Unicode code points; end-exclusive'))
    manifest=dict(processing_run_id=run_id,started_at=now(),status='running',rules_version=VERSION,documents=[])
    log(paths,'start',source_documents=len(sources),code_sha256=digest(Path(__file__).read_bytes()),rules_sha256=digest(Path(__file__).with_name('rules.py').read_bytes()),argv=sys.argv)
    for i,source in enumerate(sources,1):
        sha=source['sha256'];original=ROOT/source['path']
        record=dict(source_run_id=source['source_run_id'],asset_id=source['asset_id'],device_id=source['device_id'],
                    model=source['device']['model'],category=source['device']['category'],raw_pdf_path=source['path'],raw_pdf_sha256=sha,
                    source_url=source['source_url'],source_page=source['discovered_on'],rules_version=VERSION,
                    processing_run_id=run_id,status='processing',review_status='unreviewed')
        try:
            if digest(original.read_bytes())!=sha:raise ValueError('原始文件哈希不匹配')
            reader=PdfReader(original)
            if reader.is_encrypted:raise ValueError('加密 PDF，不能自动提取')
            raw_path=paths['extracted']/(sha+'.jsonl')
            clean_path=paths['cleaned']/(sha+'.jsonl')
            map_path=paths['cleaned']/(sha+'.map.jsonl')
            page_reports=[];rule_counts=Counter();margin_lines=Counter();margin_pages={};errors=0
            with raw_path.open('w') as raw_file,clean_path.open('w') as clean_file,map_path.open('w') as map_file:
                for page_number,page in enumerate(reader.pages,1):
                    extraction_error=None
                    try:raw=page.extract_text() or ''
                    except Exception as exc:raw='';extraction_error=str(exc);errors+=1
                    cleaned,mapping,changes=clean_page(raw)
                    flags=quality_flags(raw,cleaned)
                    if extraction_error:flags.append('extraction_error')
                    base=dict(asset_id=source['asset_id'],source_run_id=source['source_run_id'],processing_run_id=run_id,page=page_number,raw_sha256=sha)
                    raw_record=dict(base,text=raw,text_sha256=text_hash(raw),extraction_error=extraction_error)
                    clean_record=dict(base,text=cleaned,text_sha256=text_hash(cleaned),raw_text_sha256=text_hash(raw),
                                      raw_extracted_path=str(raw_path.relative_to(ROOT)),rules_version=VERSION,quality_flags=flags,review_status='unreviewed')
                    map_record=dict(base,raw_text_sha256=text_hash(raw),clean_text_sha256=text_hash(cleaned),mapping=mapping)
                    raw_file.write(json.dumps(raw_record,ensure_ascii=False)+'\n')
                    clean_file.write(json.dumps(clean_record,ensure_ascii=False)+'\n')
                    map_file.write(json.dumps(map_record,ensure_ascii=False)+'\n')
                    rule_counts.update(changes)
                    page_reports.append(dict(page=page_number,raw_characters=len(raw),clean_characters=len(cleaned),quality_flags=flags,changed=raw!=cleaned))
                    lines=[line.strip() for line in cleaned.splitlines() if line.strip()]
                    for line in set(lines[:2]+lines[-2:]):
                        if len(line)<=140:
                            margin_lines[line]+=1;margin_pages.setdefault(line,[]).append(page_number)
            if digest(original.read_bytes())!=sha:raise ValueError('处理期间原始 PDF 发生变化')
            margins=[dict(text=line,count=count,pages=margin_pages[line]) for line,count in margin_lines.items() if count>=3 and count>=len(reader.pages)*.5]
            record.update(status='completed' if not errors else 'completed_with_errors',page_count=len(reader.pages),
                extraction_errors=errors,extracted_path=str(raw_path.relative_to(ROOT)),extracted_sha256=digest(raw_path.read_bytes()),
                cleaned_path=str(clean_path.relative_to(ROOT)),cleaned_sha256=digest(clean_path.read_bytes()),
                cleaned_map_path=str(map_path.relative_to(ROOT)),cleaned_map_sha256=digest(map_path.read_bytes()),
                raw_characters=sum(p['raw_characters'] for p in page_reports),clean_characters=sum(p['clean_characters'] for p in page_reports),
                flagged_pages=sum(bool(p['quality_flags']) for p in page_reports),quality_flag_counts=dict(Counter(flag for p in page_reports for flag in p['quality_flags'])),
                changed_pages=sum(p['changed'] for p in page_reports),rule_change_counts=dict(rule_counts),pages=page_reports,
                repeated_margin_candidates=margins,note='重复边缘行只识别不删除；自动清洗完成不等于人工核验通过')
        except Exception as exc:record.update(status='failed',error=str(exc))
        manifest['documents'].append(record)
        json_write(paths['metadata']/'manifest.json',manifest)
        log(paths,'document_result',asset_id=source['asset_id'],source_run_id=source['source_run_id'],status=record['status'],pages=record.get('page_count'),flagged_pages=record.get('flagged_pages'),error=record.get('error'))
        print(f"{i}/{len(sources)} {source['asset_id']} {record['status']} pages={record.get('page_count',0)} flagged={record.get('flagged_pages',0)}",flush=True)
    manifest['completed_at']=now();manifest['status']='completed' if all(d['status']=='completed' for d in manifest['documents']) else 'needs_attention'
    json_write(paths['metadata']/'manifest.json',manifest)
    summarize(paths,manifest)
    log(paths,'finish',status=manifest['status'],manifest_sha256=digest((paths['metadata']/'manifest.json').read_bytes()))
    print('PROCESSING_RUN_ID',run_id,flush=True)


def summarize(paths,manifest):
    documents=manifest['documents'];success=[d for d in documents if d['status'] in ['completed','completed_with_errors']]
    flags=Counter(flag for d in success for p in d['pages'] for flag in p['quality_flags'])
    summary=dict(processing_run_id=manifest['processing_run_id'],status=manifest['status'],rules_version=VERSION,
        documents=len(documents),completed_documents=len(success),failed_documents=len(documents)-len(success),
        pages=sum(d['page_count'] for d in success),flagged_pages=sum(d['flagged_pages'] for d in success),
        flagged_documents=sum(bool(d['flagged_pages']) for d in success),quality_flag_counts=dict(flags),
        raw_characters=sum(d['raw_characters'] for d in success),clean_characters=sum(d['clean_characters'] for d in success),
        changed_pages=sum(d['changed_pages'] for d in success),human_reviewed_documents=0,
        note='异常标记是核验线索，不代表页面必定有错；已保留所有页面。尚未OCR、切分或向量化。')
    json_write(paths['reports']/'summary.json',summary)
    with (paths['reports']/'quality.csv').open('w',newline='',encoding='utf-8-sig') as file:
        writer=csv.writer(file);writer.writerow(['source_run_id','asset_id','model','page','flags','raw_characters','clean_characters'])
        for d in success:
            for page in d['pages']:
                if page['quality_flags']:writer.writerow([d['source_run_id'],d['asset_id'],d['model'],page['page'],';'.join(page['quality_flags']),page['raw_characters'],page['clean_characters']])
    lines=['# 文本提取与保守清洗报告','',f"处理批次：`{manifest['processing_run_id']}`。规则：`{VERSION}`。",'',
        f"处理 {summary['completed_documents']}/{summary['documents']} 份 PDF，共 {summary['pages']} 页；{summary['flagged_documents']} 份资料的 {summary['flagged_pages']} 页出现自动核验标记。",'',
        '原始 PDF 保持不变；提取文本、清洗文本、逐行区间映射分别保存。未删除页面，不补写产品参数，不自动拼词、合并连字符或重排表格。重复页眉页脚仅列为候选，不自动删除。',
        '',f"规范化前 {summary['raw_characters']:,} 字符，之后 {summary['clean_characters']:,} 字符，{summary['changed_pages']} 页有格式变化。减少的字符不等于去掉了无用知识，完整变更可由映射复核。",'',
        '## 质量标记','', '| 标记 | 页数 |','|---|---:|']
    for flag,count in flags.items():lines.append(f'| {flag} | {count} |')
    lines+=['','[待核验页 CSV](quality.csv) · [机器可读统计](summary.json)','',
        '逐页标记和重复边缘行候选在 data/metadata/processing/<本批次>/manifest.json；逐行映射在 data/processed/cleaned/<本批次>/*.map.jsonl。offset 为 Unicode 字符下标，右端不含。它是行级区间映射，不声称逐字符一一对应。',
        '', '## 当前边界','', '自动格式清洗不等于人工事实审核。扫描件/空页、疑似单词黏连、碎行、乱码和密集数字布局需要核对 PDF 原件。没有进行 OCR，也没有做文档切分或向量化。']
    (paths['reports']/'README.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(summary,ensure_ascii=False),flush=True)


def publish(run_id):
    paths=locations(run_id)
    manifest=json.loads((paths['metadata']/'manifest.json').read_text())
    if manifest['status']!='completed':raise ValueError('存在提取错误或未完成文档，请先检查，不能发布为全库完成')
    before=paths['logs']/'before-publish';before.mkdir(exist_ok=False)
    updates={(r['source_run_id'],r['asset_id']):r for r in manifest['documents']}
    # 发布前全量校验原件、产物、逐页哈希、映射覆盖和行区间。
    for record in updates.values():
        for file,expected in [(record['raw_pdf_path'],record['raw_pdf_sha256']),
             (record['extracted_path'],record['extracted_sha256']),(record['cleaned_path'],record['cleaned_sha256']),
             (record['cleaned_map_path'],record['cleaned_map_sha256'])]:
            if digest((ROOT/file).read_bytes())!=expected:raise ValueError(f'哈希不匹配 {file}')
        raw_rows=[json.loads(s) for s in (ROOT/record['extracted_path']).read_text().splitlines()]
        clean_rows=[json.loads(s) for s in (ROOT/record['cleaned_path']).read_text().splitlines()]
        map_rows=[json.loads(s) for s in (ROOT/record['cleaned_map_path']).read_text().splitlines()]
        if len(raw_rows)!=record['page_count'] or len(clean_rows)!=len(raw_rows) or len(map_rows)!=len(raw_rows):raise ValueError('页数不一致')
        for raw,clean,mapping in zip(raw_rows,clean_rows,map_rows,strict=True):
            expected,maps,_=clean_page(raw['text'])
            if expected!=clean['text'] or maps!=mapping['mapping'] or text_hash(expected)!=clean['text_sha256']:
                raise ValueError('清洗结果无法由原始页文本和规则重放')
    library=ROOT/'database/sqlite/library.sqlite3'
    if library.exists():shutil.copyfile(library,before/'library.sqlite3')
    for path in sorted((ROOT/'data/metadata/runs').glob('*/manifest.json')):
        data=json.loads(path.read_text());source_run=data['run_id']
        backup=before/source_run;backup.mkdir()
        shutil.copyfile(path,backup/'manifest.json')
        if path.with_suffix('.csv').exists():shutil.copyfile(path.with_suffix('.csv'),backup/'manifest.csv')
        for asset in data['assets']:
            record=updates.get((source_run,asset['asset_id']))
            if not record:continue
            asset.setdefault('extraction_history',[]).append({k:asset.get(k) for k in ['extracted_path','extracted_sha256','extraction_status','processing_run_id']})
            for key in ['extracted_path','extracted_sha256','cleaned_path','cleaned_sha256','cleaned_map_path','cleaned_map_sha256','processing_run_id']:
                asset[key]=record[key]
            asset.update(extraction_status='completed_unreviewed',cleaning_status='completed_unreviewed',
                         cleaning_rules_version=VERSION,quality_flag_counts=record['quality_flag_counts'],quality_flagged_pages=record['flagged_pages'])
        staging=path.with_suffix('.tmp.json');json_write(staging,data);staging.replace(path)
        csv_path=path.with_suffix('.csv')
        keys=['asset_id','device_id','kind','title','status','path','bytes','sha256','page_count','source_url','discovered_on','retrieved_at','extraction_status','cleaning_status','quality_flagged_pages']
        with csv_path.open('w',newline='',encoding='utf-8-sig') as file:
            writer=csv.DictWriter(file,fieldnames=keys,extrasaction='ignore');writer.writeheader();writer.writerows(data['assets'])
        local_db=ROOT/'database/sqlite'/source_run/'catalog.sqlite3'
        if local_db.exists():
            shutil.copyfile(local_db,backup/'catalog.sqlite3')
            with sqlite3.connect(local_db) as db:
                for asset in data['assets']:
                    if (source_run,asset['asset_id']) not in updates:continue
                    db.execute('UPDATE assets SET metadata_json=? WHERE asset_id=?',(json.dumps(asset,ensure_ascii=False),asset['asset_id']))
                    db.execute('DELETE FROM pages WHERE asset_id=?',(asset['asset_id'],))
                    for line in (ROOT/asset['extracted_path']).read_text().splitlines():
                        row=json.loads(line);db.execute('INSERT INTO pages VALUES(?,?,?,?)',(asset['asset_id'],row['page'],row['text'],row['raw_sha256']))
        log(paths,'source_catalog_updated',source_run_id=source_run,manifest_sha256=digest(path.read_bytes()))
    from pipelines.collection.build_library import build
    build(minimum=100)
    log(paths,'published',library_sha256=digest(library.read_bytes()),documents=len(updates))
    json_write(paths['metadata']/'publication.json',dict(published_at=now(),documents=len(updates),library_sha256=digest(library.read_bytes())))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['run','publish'])
    parser.add_argument('--run-id',default='cleaning_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    args=parser.parse_args();run(args.run_id) if args.command=='run' else publish(args.run_id)
