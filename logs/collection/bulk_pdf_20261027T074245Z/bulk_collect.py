"""扩充官方公开 PDF：限速、来源快照、跨批次内容去重、可恢复清单。"""
import argparse
import csv
import hashlib
import io
import json
import re
import sqlite3
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urljoin,urlsplit,unquote
from bs4 import BeautifulSoup
from pypdf import PdfReader
from .collect_sample import Collector, CATEGORY_DIRS, digest, now
from .layout import ROOT


def existing_pdfs(exclude_run=None):
    found={}
    urls=set()
    for manifest in sorted((ROOT/'data/metadata/runs').glob('*/manifest.json')):
        if manifest.parent.name==exclude_run:
            continue
        data=json.loads(manifest.read_text())
        for asset in data['assets']:
            if asset['status']=='downloaded' and asset.get('path','').lower().endswith('.pdf'):
                path=ROOT/asset['path']
                if path.exists() and digest(path.read_bytes())==asset['sha256']:
                    found[asset['sha256']]=asset['path']
                    urls.add(asset['source_url'])
    return found,urls


def pdf_kind(title,url):
    text=(title+' '+unquote(url)).lower()
    if any(x in text for x in ['declaration','conformity','discontinuation','mtbf','dimension','flyer','brochure','offerings','a&e spec']):
        return None
    if 'datasheet' in text or 'data-sheet' in text or 'data sheet' in text:
        return 'datasheet'
    if 'wiring' in text:
        return 'wiring'
    if any(x in text for x in ['user manual','user-manual','um_','operating instruction','operation manual']):
        return 'user_manual'
    if 'installation' in text or 'install guide' in text:
        return 'installation'
    if 'manual' in text or 'instructions' in text or 'quick guide' in text:
        return 'manual'
    if 'comparison-table-of-axis-network-door' in text:
        return 'comparison'
    return None


class BulkCollector(Collector):
    def __init__(self,run_id,target):
        super().__init__(run_id)
        self.target=target
        self.known,self.seen_urls=existing_pdfs(exclude_run=run_id)
        self.baseline_count=len(self.known)
        self.devices={}
        self.source_urls=set()
        self.attempted=set()
        self.source_records=[]
        (self.layout.logs/'bulk_collect.py').write_bytes(Path(__file__).read_bytes())
        self.log('bulk_start',baseline_unique_pdfs=self.baseline_count,target_total_unique_pdfs=target,
                 code_sha256=digest(Path(__file__).read_bytes()),criteria='官方公开参数表/手册/安装接线资料；不以证书/尺寸图/宣传册补数；按 SHA-256 跨轮去重')

    def reached(self):
        return len(self.known)>=self.target

    def source(self,url):
        key=digest(url.encode())[:16]
        try:
            body,meta=self.request(url,limit=15_000_000)
            path=self.layout.sources/(key+'.html')
            path.write_bytes(body)
            record=dict(meta,sha256=digest(body),snapshot=self.layout.relative(path),source_id=key)
            (self.layout.source_metadata/(key+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2))
            self.source_records.append(record)
            return BeautifulSoup(body,'html.parser')
        except Exception as exc:
            self.log('source_failed',url=url,error=str(exc))
            print('SOURCE FAILED',url,str(exc)[:100],flush=True)
            return None

    def asset(self,device,title,url,kind,page):
        if self.reached() or url in self.attempted:
            return
        self.attempted.add(url)
        if url in self.seen_urls:
            self.log('known_url_skipped',url=url,source_page=page)
            return
        if urlsplit(url).hostname not in ['www.axis.com','help.axis.com','optex.imgix.net','navi.optex.net']:
            self.log('out_of_scope_link',url=url,source_page=page)
            return
        a=dict(asset_id=f'B{len(self.assets)+1:04}',device_id=device['device_id'],kind=kind,title=title,
               status='pending',source_url=url,discovered_on=page,path=None,sha256=None,bytes=None,
               page_count=None,review_status='unreviewed',extraction_status='not_started')
        self.assets.append(a)
        try:
            body,meta=self.request(url)
            a.update(meta)
            if not body.startswith(b'%PDF-'):
                raise ValueError('响应不是 PDF（可能是网页或认证提示），未保存为原件')
            h=digest(body)
            if h in self.known:
                a.update(status='duplicate',sha256=h,duplicate_of=self.known[h])
                self.seen_urls.add(url)
                return
            reader=PdfReader(io.BytesIO(body))
            if reader.is_encrypted:
                raise PermissionError('加密 PDF，交给人工核验')
            count=len(reader.pages)
            if not count:
                raise ValueError('PDF 没有页面')
            path=self.layout.pdfs/CATEGORY_DIRS[device['category']]/device['device_id']/(a['asset_id']+'_'+kind+'.pdf')
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(body)
            a.update(status='downloaded',path=self.layout.relative(path),sha256=h,bytes=len(body),page_count=count,
                     original_url_filename=unquote(urlsplit(url).path.rsplit('/',1)[-1]))
            self.known[h]=a['path'];self.seen_urls.add(url)
            print(f"UNIQUE {len(self.known)}/{self.target} | {device['category']} | {device['model']} | {kind} | {count} pages",flush=True)
        except Exception as exc:
            a.update(status='manual_required' if isinstance(exc,PermissionError) else 'failed',error=str(exc))
            print(a['status'],url,str(exc)[:80],flush=True)
        finally:
            self.log('asset_result',**a)
            self.export()

    def export(self):
        if not hasattr(self,'devices'):
            return
        manifest=dict(layout_version=2,path_base='project_root',run_id=self.layout.run_id,
                      devices=list(self.devices.values()),assets=self.assets,
                      policy=dict(target_total_unique_pdfs=self.target,baseline_unique_pdfs=self.baseline_count,
                                  global_unique_pdfs=len(self.known),extraction='not_started',counting='SHA-256 distinct readable PDFs'))
        (self.output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
        fields=['asset_id','device_id','kind','title','status','path','bytes','page_count','sha256','source_url','discovered_on','retrieved_at','error','duplicate_of']
        with (self.output/'manifest.csv').open('w',newline='',encoding='utf-8-sig') as file:
            w=csv.DictWriter(file,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(self.assets)
        with sqlite3.connect(self.layout.database) as db:
            db.executescript((ROOT/'database/sqlite/schema.sql').read_text())
            for d in self.devices.values():
                db.execute('INSERT OR REPLACE INTO devices VALUES(?,?,?,?,?)',tuple(d[k] for k in ['device_id','brand','model','category','source_page']))
            for a in self.assets:
                db.execute('INSERT OR REPLACE INTO assets VALUES(?,?,?,?,?,?,?,?)',(a['asset_id'],a['device_id'],a['kind'],a['title'],a['status'],a['path'],a['sha256'],json.dumps(a,ensure_ascii=False)))
        status=Counter(a['status'] for a in self.assets)
        by_category=Counter(self.devices[a['device_id']]['category'] for a in self.assets if a['status']=='downloaded')
        summary=dict(at=now(),run_id=self.layout.run_id,baseline_unique_pdfs=self.baseline_count,
                     total_unique_pdfs=len(self.known),new_status_counts=dict(status),new_pdf_categories=dict(by_category),
                     new_pdf_pages=sum(a.get('page_count') or 0 for a in self.assets if a['status']=='downloaded'),
                     new_pdf_bytes=sum(a.get('bytes') or 0 for a in self.assets if a['status']=='downloaded'))
        (self.layout.reports/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))

    def optex(self,pages=16,max_new=32):
        before=len(self.known)
        visited=set()
        for number in range(1,pages+1):
            if self.reached() or len(self.known)-before>=max_new:
                break
            url='https://www.optex-europe.com/support/downloads'+(f'?page={number}' if number>1 else '')
            soup=self.source(url)
            if soup is None:continue
            links=soup.select('a[href]')
            candidates=[]
            for a in links:
                href=urljoin(url,a['href'])
                if '.pdf' not in href.lower():continue
                row=a.parent.parent
                text=' '.join(row.stripped_strings)
                if 'security' not in text.lower() and 'intrusion' not in text.lower() and 'Intrusion-Detection' not in href:
                    continue
                kind=pdf_kind(text,href)
                if not kind:continue
                matches=re.findall(r'\b[A-Z][A-Z0-9]{1,10}-[A-Z0-9][A-Z0-9-]*',text)
                model=matches[0] if matches else 'family-'+digest(href.encode())[:10]
                sid='optex-'+model.lower()
                device=dict(device_id=sid,brand='OPTEX',model=model,category='入侵报警',source_page=url,
                            identity_status='catalog_label_requires_review',catalog_context=text[:700])
                self.devices[sid]=device
                candidates.append((device,text[:500],href,kind))
            signature=tuple(c[2] for c in candidates)
            if signature in visited:
                self.log('pagination_repeated',url=url)
                break
            visited.add(signature)
            for device,title,href,kind in candidates:
                self.asset(device,title,href,kind,url)
                if self.reached() or len(self.known)-before>=max_new:break
        print('OPTEX new unique',len(self.known)-before,flush=True)

    def axis_queue(self):
        url='https://help.axis.com/en-us/'
        soup=self.source(url)
        if soup is None:return []
        categories={'Network door controllers':'门禁','Network intercoms':'对讲',
                    'Bullet cameras':'视频监控','Dome cameras':'视频监控','Box cameras':'视频监控','PTZ cameras':'视频监控'}
        groups={k:[] for k in categories}
        current=''
        for node in soup.find_all(['h2','a']):
            if node.name=='h2':current=node.get_text(' ',strip=True);continue
            href=node.get('href','')
            if current not in categories or not href:continue
            slug=urlsplit(href).path.rstrip('/').split('/')[-1]
            if not re.fullmatch(r'axis-[a-z0-9-]+',slug):continue
            groups[current].append(dict(slug=slug,category=categories[current],label=node.get_text(' ',strip=True),
                                        discovered_on=url,manual_url=urljoin(url,href),
                                        support_url='https://www.axis.com/products/'+slug+'/support'))
        # 门禁和对讲优先，视频监控按外形类别轮询，避免只抓某一种摄像机。
        queue=groups['Network door controllers']+groups['Network intercoms']
        cameras=[groups[k] for k in ['Bullet cameras','Dome cameras','Box cameras','PTZ cameras']]
        for i in range(max(map(len,cameras),default=0)):
            queue.extend(group[i] for group in cameras if i<len(group))
        seen=set();result=[]
        for row in queue:
            if row['support_url'] not in seen:
                result.append(row);seen.add(row['support_url'])
        (self.layout.source_metadata/'axis-candidates.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
        return result

    def axis(self):
        for candidate in self.axis_queue():
            if self.reached():break
            page=candidate['support_url']
            soup=self.source(page)
            if soup is None:continue
            heading=soup.find('h1')
            title=heading.get_text(' ',strip=True) if heading else ''
            if 'AXIS' not in title.upper():
                self.log('product_page_unconfirmed',url=page,title=title);continue
            sid=candidate['slug']
            model=re.sub(r'^Product support for\s*','',title,flags=re.I)
            self.devices[sid]=dict(device_id=sid,brand='AXIS',model=model,category=candidate['category'],source_page=page,
                                   discovered_on=candidate['discovered_on'],manual_url=candidate['manual_url'],
                                   identity_status='official_support_heading',support_url_derivation='由官方文档目录中的产品 slug 构造并通过响应标题核对',
                                   lifecycle_note='目录含历史产品；是否停产需另行核验')
            for a in soup.select('a[href]'):
                href=urljoin(page,a['href'])
                if '.pdf' not in href.lower() or '/dam/partner/' in href:continue
                row=a.find_parent('li') or a.parent.parent
                context=' '.join(row.stripped_strings)
                if 'Requires partner access' in context:continue
                kind=pdf_kind(context,href)
                if kind:self.asset(self.devices[sid],context[:700],href,kind,page)
                if self.reached():break

    def run_bulk(self):
        try:
            self.optex()
            self.axis()
        finally:
            self.export()
            self.log('bulk_finish',global_unique_pdfs=len(self.known),target=self.target,reached=self.reached())
            self.client.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--target-total',type=int,default=110)
    p.add_argument('--run-id',default='bulk_pdf_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    args=p.parse_args()
    if not 100<=args.target_total<=500:raise SystemExit('target-total 本轮限制为100到500')
    collector=BulkCollector(args.run_id,args.target_total)
    print('RUN_ID',args.run_id,'BASELINE',collector.baseline_count,flush=True)
    collector.run_bulk()
    print('RESULT',len(collector.known),'unique PDFs',flush=True)
