"""Render 只读演示入口；不加载数据写入或 PostgreSQL 管理路由。"""
import os
import secrets
from pathlib import Path
from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from .config import settings
from .library import router, database


def authorize(x_api_key: str | None = Header(default=None)):
    expected = settings().api_key
    if expected and not secrets.compare_digest(x_api_key or '', expected):
        raise HTTPException(401, '需要有效的 X-API-Key')


def create_app(static_directory=None):
    app = FastAPI(title='Sentinel 只读资料演示', docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware('http')
    async def read_only(request, call_next):
        # 公网演示不能通过请求启用远程付费模型或向量服务。
        if request.url.path == '/api/library/search' and request.method == 'POST':
            try:
                body = await request.json()
            except ValueError:
                body = None
            if isinstance(body, dict) and body.get('generate'):
                from fastapi.responses import JSONResponse
                return JSONResponse({'detail': '公开演示仅支持证据检索，模型生成未开放'}, status_code=403)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

    @app.get('/api/health')
    def health():
        with database() as db:
            db.execute('SELECT 1 FROM assets LIMIT 1').fetchone()
        return {'status': 'ok', 'mode': 'read_only_demo'}

    app.include_router(router, dependencies=[Depends(authorize)])
    directory = Path(static_directory or os.environ.get('FRONTEND_DIST', 'frontend/dist'))
    app.mount('/', StaticFiles(directory=directory, html=True), name='frontend')
    return app
