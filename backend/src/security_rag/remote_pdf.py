"""仅允许登记的厂商地址；下载结果必须与采集时 SHA-256 完全一致。"""
import hashlib
import time
from collections import OrderedDict
from threading import Lock, BoundedSemaphore
from urllib.parse import urlsplit, urljoin
import httpx
from fastapi import HTTPException

ALLOWED_HOSTS = {'www.axis.com', 'axis.com', 'optex.imgix.net'}
MAX_BYTES = 32 * 1024 * 1024
CACHE_BYTES = 48 * 1024 * 1024
_cache = OrderedDict()
_lock = Lock()
_downloads = BoundedSemaphore(2)


def check_url(url):
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.hostname not in ALLOWED_HOSTS or parts.username or parts.password or parts.port not in (None, 443):
        raise HTTPException(502, '原件来源地址不在允许范围')


def fetch_pdf(url, expected_sha):
    if not _downloads.acquire(blocking=False):
        raise HTTPException(429, '原件读取繁忙，请稍后重试')
    try:
        return _fetch_pdf(url, expected_sha)
    finally:
        _downloads.release()


def _fetch_pdf(url, expected_sha):
    with _lock:
        if expected_sha in _cache:
            _cache.move_to_end(expected_sha)
            return _cache[expected_sha]
    started = time.monotonic()
    try:
        with httpx.Client(timeout=15, follow_redirects=False, trust_env=False) as client:
            for _ in range(4):
                check_url(url)
                with client.stream('GET', url, headers={'User-Agent': 'SecurityRAG/0.1 (official document preview)'}) as response:
                    if response.is_redirect:
                        url = urljoin(url, response.headers.get('location', ''))
                        continue
                    response.raise_for_status()
                    content = bytearray()
                    for block in response.iter_bytes():
                        content.extend(block)
                        if len(content) > MAX_BYTES or time.monotonic() - started > 40:
                            raise HTTPException(502, '原件超出读取大小或时间限制')
                    data = bytes(content)
                    if not data.startswith(b'%PDF-') or hashlib.sha256(data).hexdigest() != expected_sha:
                        raise HTTPException(502, '官方原件已变化或不是预期 PDF，请从来源页面核对')
                    with _lock:
                        while _cache and sum(map(len, _cache.values())) + len(data) > CACHE_BYTES:
                            _cache.popitem(last=False)
                        _cache[expected_sha] = data
                    return data
    except httpx.HTTPError as exc:
        raise HTTPException(502, '官方原件暂时无法读取，请打开资料中的官方来源链接') from exc
    raise HTTPException(502, '官方原件重定向过多')
