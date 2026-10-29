"""下载小型官方样本：独立运行目录、原件哈希、日志、SQLite 目录。

不使用浏览器 cookies，不登录，不绕过验证码、DRM 或站点限制。
"""
import argparse
import csv
import hashlib
import io
import json
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit, unquote

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader
from .discover_sources import SOURCES
from .layout import ROOT, DatasetLayout

CATEGORY_DIRS = {"视频监控":"video_surveillance","门禁":"access_control","对讲":"intercom","入侵报警":"intrusion_alarm"}

USER_AGENT = "BuildingSecurityResearch/0.1 (small academic sample)"


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def robots_allowed(text, url):
    """支持公开 robots 中 * / $ 匹配，最长规则优先。仅解析适用的 * 组。"""
    applicable = False
    previous_directive = False
    rules = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, value = [part.strip() for part in line.split(":", 1)]
        key = key.lower()
        if key == "user-agent":
            if previous_directive:
                applicable = False
            applicable = applicable or value == "*"
            previous_directive = False
        elif key in ("allow", "disallow"):
            previous_directive = True
            if applicable and value:
                pattern = re.escape(value).replace(r"\*", ".*")
                if value.endswith("$"):
                    pattern = pattern[:-2] + "$"
                if re.match(pattern, urlsplit(url).path + ("?" + urlsplit(url).query if urlsplit(url).query else "")):
                    rules.append((len(value.replace("*", "").rstrip("$")), key == "allow"))
    return max(rules, default=(0, True))[1]


class Collector:
    def __init__(self, run_id):
        self.layout = DatasetLayout(run_id)
        self.layout.initialize()
        self.output = self.layout.metadata
        (self.layout.logs / "collector.py").write_bytes(Path(__file__).read_bytes())
        (self.layout.logs / "uv.lock").write_bytes((ROOT / "uv.lock").read_bytes())
        self.assets, self.robots = [], {}
        self.client = httpx.Client(timeout=60, follow_redirects=False, headers={"User-Agent": USER_AGENT})
        self.log("run_start", python=sys.version, code_sha256=digest(Path(__file__).read_bytes()),
                 uv_lock_sha256=digest((ROOT / "uv.lock").read_bytes()), argv=sys.argv,
                 settings={"delay_seconds":1,"max_pdf_bytes":50_000_000,"video_max_height":480,"max_video_bytes":200_000_000})

    def log(self, event, **data):
        with (self.layout.logs / "events.jsonl").open("a") as file:
            file.write(json.dumps({"at": now(), "event":event, **data}, ensure_ascii=False) + "\n")

    def request(self, url, limit=50_000_000, check_robots=True):
        # 显式检查每次重定向，认证入口一律交给人工。
        original = url
        for _ in range(6):
            if re.search(r"/(login|signin|sign-in|my-axis|user/login)(/|\?|$)", url, re.I):
                raise PermissionError("重定向到登录入口")
            if check_robots:
                origin = f"{urlsplit(url).scheme}://{urlsplit(url).netloc}"
                if origin not in self.robots:
                    robot_url = origin + "/robots.txt"
                    r = self.client.get(robot_url)
                    self.log("robots", url=robot_url, status=r.status_code, sha256=digest(r.content))
                    name = urlsplit(url).netloc + "-robots.txt"
                    (self.layout.sources / name).write_bytes(r.content)
                    if r.status_code == 200:
                        self.robots[origin] = r.text
                    elif r.status_code == 404:
                        self.robots[origin] = ""
                    else:
                        raise PermissionError(f"robots.txt 无法确认，状态 {r.status_code}")
                if not robots_allowed(self.robots[origin],url):
                    raise PermissionError("robots.txt 禁止自动获取此路径；可由用户手工查看下载")
            time.sleep(1)
            with self.client.stream("GET", url) as response:
                self.log("http_response", url=url,status=response.status_code,
                         headers={k:response.headers.get(k) for k in ("content-type","content-length","etag","last-modified","location")})
                if response.status_code in (401,403):
                    raise PermissionError(f"HTTP {response.status_code}：需人工确认访问权限或站点拦截")
                if response.is_redirect:
                    url = urljoin(url,response.headers["location"])
                    continue
                response.raise_for_status()
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > limit:
                        raise ValueError("超过本轮文件大小限制")
                return bytes(data), {"requested_url":original,"final_url":str(response.url),"retrieved_at":now(),
                                     "http_status":response.status_code,"content_type":response.headers.get("content-type"),
                                     "etag":response.headers.get("etag"),"last_modified":response.headers.get("last-modified")}
        raise ValueError("过多重定向")

    def pdf(self, device, title, url, kind, discovered_on):
        asset = dict(asset_id=f"A{len(self.assets)+1:03}",device_id=device[0],title=title,
                     source_url=url,discovered_on=discovered_on,kind=kind,status="pending",path=None,
                     sha256=None,bytes=None,page_count=None,error=None,review_status="unreviewed")
        self.assets.append(asset)
        try:
            content, meta = self.request(url)
            asset.update(meta)
            if not content.startswith(b"%PDF-"):
                raise ValueError("响应不是 PDF，可能返回认证或拦截页")
            reader = PdfReader(io.BytesIO(content))
            if reader.is_encrypted:
                raise PermissionError("PDF 已加密，交给人工处理")
            name = f"{asset['asset_id']}_{device[0]}_{kind}.pdf"
            path = self.layout.pdfs / CATEGORY_DIRS[device[3]] / device[0] / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            asset.update(status="downloaded",path=str(path.relative_to(ROOT)),sha256=digest(content),
                         bytes=len(content),page_count=len(reader.pages),original_url_filename=unquote(urlsplit(url).path.rsplit('/',1)[-1]))
            # 仅提取，不清洗、不重排表格、不切分；保留逐页原始文本。
            extracted = self.layout.pages / (path.stem + ".jsonl")
            try:
                with extracted.open("w") as file:
                    for number,page in enumerate(reader.pages,1):
                        text = page.extract_text() or ""
                        file.write(json.dumps({"asset_id":asset["asset_id"],"raw_sha256":asset["sha256"],
                                              "page":number,"text":text,"text_sha256":digest(text.encode())},ensure_ascii=False)+"\n")
                asset["extracted_path"] = str(extracted.relative_to(ROOT))
                asset["extracted_sha256"] = digest(extracted.read_bytes())
                asset["extraction_status"] = "completed"
            except Exception as exc:
                asset["extraction_status"] = "failed"
                asset["extraction_error"] = str(exc)
            print(asset['asset_id'],device[2],kind,"downloaded",len(content),flush=True)
        except Exception as exc:
            asset.update(status="manual_required" if isinstance(exc,PermissionError) else "failed",error=str(exc))
            print(asset['asset_id'],device[2],kind,asset['status'],str(exc),flush=True)
        finally:
            self.log("asset_result",**asset)
            self.export()

    def video(self, device, url, title, discovered_on):
        asset = dict(asset_id=f"A{len(self.assets)+1:03}",device_id=device[0],title=title,
                     source_url=url,discovered_on=discovered_on,kind="video",status="pending",path=None,
                     sha256=None,bytes=None,page_count=None,error=None,review_status="unreviewed")
        self.assets.append(asset)
        prefix = f"{asset['asset_id']}_{device[0]}"
        logfile = self.layout.logs / (prefix + "-video.log")
        # 无 cookies、无代理变更、无 DRM/登录绕过；认证失败即停止该视频。
        command = [sys.executable,"-m","yt_dlp","--no-playlist","--no-progress","--no-warnings",
                   "--socket-timeout","25","--retries","1","--fragment-retries","1",
                   "--max-filesize","200M","--format","best[height<=480][ext=mp4]/best[height<=480]",
                   "--write-info-json","--no-write-playlist-metafiles",
                   "--output",str(self.layout.videos / (prefix+".%(ext)s")),url]
        self.log("video_command",command=command,source_page=discovered_on)
        try:
            with logfile.open("w") as log:
                result = subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=180)
            files = [p for p in (self.layout.videos).glob(prefix+".*") if p.suffix in (".mp4",".webm",".mkv")]
            if result.returncode != 0 or not files:
                reason = logfile.read_text()[-1800:]
                asset["status"] = "manual_required" if re.search(r"sign.in|log.in|bot|403|captcha|private|confirm",reason,re.I) else "failed"
                raise RuntimeError(reason or "未生成视频文件（可能超过大小限制）")
            path = files[0]
            probe = subprocess.run(["ffprobe","-v","error","-show_format","-show_streams","-of","json",str(path)],capture_output=True,text=True,check=True)
            info = json.loads(probe.stdout)
            if not any(stream["codec_type"] == "video" for stream in info["streams"]):
                raise ValueError("未找到视频流")
            asset.update(status="downloaded",path=str(path.relative_to(ROOT)),bytes=path.stat().st_size,
                         sha256=digest(path.read_bytes()),retrieved_at=now(),duration_seconds=float(info["format"]["duration"]))
            (self.layout.logs/(prefix+"-ffprobe.json")).write_text(probe.stdout)
            print(asset['asset_id'],device[2],"video downloaded",flush=True)
        except Exception as exc:
            if asset["status"] == "pending":
                asset["status"] = "failed"
            asset["error"] = str(exc)
            print(asset['asset_id'],device[2],"video",asset['status'],flush=True)
        finally:
            self.log("asset_result",**asset)
            self.export()

    def export(self):
        (self.output/"manifest.json").write_text(json.dumps({"devices":[dict(zip(("device_id","brand","model","category","source_page"),d)) for d in SOURCES],"assets":self.assets,"layout_version":2,"path_base":"project_root","run_id":self.layout.run_id},ensure_ascii=False,indent=2))
        columns = ["asset_id","device_id","kind","title","status","path","bytes","sha256","page_count","source_url","discovered_on","retrieved_at","error"]
        with (self.output/"manifest.csv").open("w",newline="",encoding="utf-8-sig") as file:
            writer=csv.DictWriter(file,fieldnames=columns,extrasaction="ignore");writer.writeheader();writer.writerows(self.assets)
        with sqlite3.connect(self.layout.database) as db:
            db.executescript((ROOT / "database/sqlite/schema.sql").read_text())
            for d in SOURCES:
                db.execute("INSERT OR REPLACE INTO devices VALUES(?,?,?,?,?)",d)
            for a in self.assets:
                db.execute("INSERT OR REPLACE INTO assets VALUES(?,?,?,?,?,?,?,?)",(a["asset_id"],a["device_id"],a["kind"],a["title"],a["status"],a["path"],a["sha256"],json.dumps(a,ensure_ascii=False)))
                if a.get("extracted_path"):
                    for line in (ROOT/a["extracted_path"]).read_text().splitlines():
                        page=json.loads(line)
                        db.execute("INSERT OR REPLACE INTO pages VALUES(?,?,?,?)",(a["asset_id"],page["page"],page["text"],page["raw_sha256"]))

    def run(self, videos=True):
        for device in SOURCES:
            page = ROOT/"data/raw/webpages/source_catalog"/(device[0]+".html")
            # 把已获取的来源快照及其元数据复制到本轮目录，避免后续外部文件变化。
            for ext in (".html",".json"):
                src=page if ext == ".html" else ROOT/"data/metadata/source_catalog"/(device[0]+ext)
                ((self.layout.sources if ext == ".html" else self.layout.source_metadata)/src.name).write_bytes(src.read_bytes())
            self.log("source_snapshot_import",source_id=device[0],path=page.name,sha256=digest(page.read_bytes()))
            soup=BeautifulSoup(page.read_bytes(),"html.parser")
            selected={}
            for a in soup.select("a[href]"):
                url=urljoin(device[4],a['href'])
                parent=a.find_parent("li") or a.parent.parent
                title=" ".join(parent.stripped_strings)
                if '.pdf' not in url.lower() or '/dam/partner/' in url:
                    continue
                kind = ('installation' if 'installation-guide' in url or 'installation guide' in title.lower() else
                        'datasheet' if 'datasheet' in url.lower() else
                        'wiring' if 'electrical-wiring' in url else
                        'comparison' if 'comparison-table-of-axis-network-door' in url else None)
                if kind and kind not in selected:
                    selected[kind]=(title,url)
            for kind,(title,url) in selected.items():
                self.pdf(device,title,url,kind,device[4])
            if device[0].startswith('optex'):
                manual='https://navi.optex.net/manual/50447/5931691-00%20FLX-P-ST_DT%20MANUAL_EN%2020240327op_web.pdf'
                self.pdf(device,'FlipX Professional Installation Instructions (English; series variants)',manual,'installation','https://navi.optex.net/manual/50447/')
            if videos:
                for frame in soup.select('iframe[src]'):
                    match=re.search(r'youtube.com/embed/([\w-]+)',frame['src'])
                    if match:
                        self.video(device,'https://www.youtube.com/watch?v='+match[1],'Official product support embedded video',device[4])
        self.log("run_complete",counts={status:sum(a['status']==status for a in self.assets) for status in {a['status'] for a in self.assets}})
        self.export()


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--run-id',default='security_sample_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    parser.add_argument('--skip-videos',action='store_true')
    args=parser.parse_args()
    collector=Collector(args.run_id)
    try:
        collector.run(not args.skip_videos)
    finally:
        collector.client.close()
        collector.export()
    print('OUTPUT',collector.output,flush=True)
