"""维护命令：初始化、JSON 入库、文本型 PDF 分页入库。"""
import argparse
import json
from pathlib import Path
from pypdf import PdfReader
from .config import settings
from .db import init_db, init_compatibility
from .models import IngestRequest
from .service import KnowledgeBase


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db")
    ingest = sub.add_parser("ingest")
    ingest.add_argument("json_file", type=Path)
    pdf = sub.add_parser("ingest-pdf")
    pdf.add_argument("pdf_file", type=Path)
    pdf.add_argument("metadata_file", type=Path, help="与 JSON 入库字段相同，但无需 text/page")
    args = parser.parse_args()
    cfg = settings()
    if args.command == "init-db":
        init_db(cfg)
        init_compatibility(cfg)
        print("数据库初始化完成")
    elif args.command == "ingest":
        body = IngestRequest.model_validate_json(args.json_file.read_text())
        print(json.dumps(KnowledgeBase(cfg).ingest(body), ensure_ascii=False))
    else:
        reader = PdfReader(args.pdf_file)
        meta = json.loads(args.metadata_file.read_text())
        # 先验证整份文档，不允许扫描件或空页悄悄被当作成功入库。
        pages = []
        for number, page in enumerate(reader.pages, 1):
            text = (page.extract_text() or "").strip()
            if len(text) < 10:
                raise ValueError(f"第 {number} 页文本不足，请先 OCR 或清理空白页后再入库")
            pages.append(IngestRequest.model_validate(dict(meta, text=text, page=number,
                         source_key=f"{meta['source_key']}:page:{number}")))
        for page in pages:
            print(json.dumps(KnowledgeBase(cfg).ingest(page), ensure_ascii=False))
        print("分页入库完成。PDF 页数减少时旧页面需人工清理；跨页操作暂非单一事务。")


if __name__ == "__main__":
    main()
