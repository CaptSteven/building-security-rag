"""项目相对路径为清单唯一规范；数据、数据库、报告、日志分别落盘。"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class DatasetLayout:
    def __init__(self, run_id: str, root: Path = ROOT):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", run_id):
            raise ValueError("run_id 只能包含字母、数字、下划线和连字符")
        self.root = root
        self.run_id = run_id
        self.metadata = root / "data/metadata/runs" / run_id
        self.pdfs = root / "data/raw/pdfs" / run_id
        self.videos = root / "data/raw/videos" / run_id
        self.sources = root / "data/raw/webpages" / run_id
        self.source_metadata = root / "data/metadata/source_snapshots" / run_id
        self.pages = root / "data/interim/extracted" / run_id / "v1"
        self.pages_v2 = root / "data/interim/extracted" / run_id / "v2"
        self.logs = root / "logs/collection" / run_id
        self.previews = root / "reports/previews" / run_id
        self.reports = root / "reports/datasets" / run_id
        self.database = root / "database/sqlite" / run_id / "catalog.sqlite3"
        self.inbox = root / "data/inbox" / run_id

    def initialize(self):
        self.metadata.mkdir(parents=True, exist_ok=False)
        for p in (self.pdfs,self.videos,self.sources,self.source_metadata,self.pages,self.pages_v2,self.logs,
                  self.previews,self.reports,self.database.parent,self.inbox):
            p.mkdir(parents=True, exist_ok=True)

    def relative(self, path: Path):
        return str(path.relative_to(self.root))
