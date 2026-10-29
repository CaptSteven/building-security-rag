"""保存官方产品页快照并列出 PDF/视频链接；不批量遍历站点。"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
import httpx
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research/catalog"
OUT.mkdir(parents=True, exist_ok=True)
SOURCES = [
    ("axis-m2035-le", "AXIS", "M2035-LE", "视频监控", "https://www.axis.com/products/axis-m2035-le/support"),
    ("axis-a1210", "AXIS", "A1210", "门禁", "https://www.axis.com/products/axis-a1210/support"),
    ("axis-i8116-e", "AXIS", "I8116-E", "对讲", "https://www.axis.com/products/axis-i8116-e/support"),
    ("optex-flx-p-dt", "OPTEX", "FLX-P-DT", "入侵报警", "https://www.optex-europe.com/products/intrusion-detection/flx-p-dt-flipx-professional-indoor-pir-with-dual-technology-"),
]
if __name__ == "__main__":
    for sid, brand, model, category, url in SOURCES:
        response = httpx.get(url, timeout=45, follow_redirects=True, headers={"User-Agent": "BuildingSecurityResearch/0.1 (small academic sample)"})
        response.raise_for_status()
        path = OUT / f"{sid}.html"
        path.write_bytes(response.content)
        meta = {"source_id":sid,"brand":brand,"model":model,"category":category,"url":url,
                "final_url":str(response.url),"retrieved_at":datetime.now(timezone.utc).isoformat(),
                "status":response.status_code,"sha256":hashlib.sha256(response.content).hexdigest(),"snapshot":str(path.relative_to(ROOT))}
        (OUT / f"{sid}.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2))
        soup = BeautifulSoup(response.content,"html.parser")
        print("\nSOURCE",sid)
        for a in soup.select("a[href]"):
            link = urljoin(str(response.url), a["href"])
            if ".pdf" in link.lower() or "navi.optex.net/manual" in link or "youtube" in link or "vimeo" in link:
                parent=a.find_parent("li") or a.parent.parent
                context = " ".join(parent.stripped_strings)
                print(json.dumps({"url":link,"context":context[:350]},ensure_ascii=False))
        for el in soup.select("iframe, video, source"):
            print("VIDEO",str(el)[:1500])
