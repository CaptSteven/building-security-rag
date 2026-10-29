"""JSONL 按真实 LF/CRLF 读取，不能用 str.splitlines 拆开字符串内 Unicode 分隔符。"""
import json
from pathlib import Path


def read_jsonl(path: Path):
    with path.open(encoding='utf-8',newline='') as file:
        for line in file:
            if line.strip():
                yield json.loads(line)
