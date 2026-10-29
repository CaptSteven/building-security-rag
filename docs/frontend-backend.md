# 前后端实现与边界

前端：React/TypeScript/Vite 独立应用，默认 127.0.0.1:5173。
后端：FastAPI，默认 127.0.0.1:8000；保留原有 PostgreSQL RAG 接口。
资料底座：database/sqlite/library.sqlite3，只读连接。PDF 位于 data/raw/pdfs/，由后端按清单定位后返回；前端不能请求任意磁盘路径。

## 本地启动

在项目根目录：

```bash
uv sync --group collection --group dev
npm --prefix frontend ci
uv run python backend/dev.py
```

不需要 PostgreSQL 或模型密钥即可浏览资料和检索已有页文本。浏览器打开 http://127.0.0.1:5173/。Ctrl+C 同时关闭本轮前后端进程。

也可用两个终端分别运行 `uv run uvicorn security_rag.api:app --host 127.0.0.1 --port 8000` 和 `npm --prefix frontend run dev`。Vite 只代理 /api，开发端口必须与上述配置一致。

## 只读资料接口

| 接口 | 行为 |
|---|---|
| GET /api/health | API 进程健康状态，不依赖 PostgreSQL |
| GET /api/library/summary | PDF 数量、页数、类别、已提取文本与批次 |
| GET /api/library/documents | q/category/brand/kind/extraction 筛选和 page/page_size 分页 |
| GET /api/library/documents.csv | 导出完整资料清单 |
| GET /api/library/documents/{run_id}/{asset_id} | 元数据与少量提取文本预览 |
| GET /api/library/documents/{run_id}/{asset_id}/file | 返回清单中已登记的 PDF 原件 |
| POST /api/library/search | text_source=raw/cleaned 选择页文本关键词查询，可选基于证据生成回答 |
| GET /api/library/connections | 配置状态，不返回密钥，不声称远程服务已连通 |
| GET /api/library/processing | 最新清洗批次、规则、质量标记和样例 |
| GET /api/library/processing/quality.csv | 导出有标记的逐页核验清单 |
| GET /api/library/attention | 未成功或需人工处理的采集项 |

所有 /api/library 接口使用既有 API_KEY / X-API-Key 认证配置。默认本机使用未设置访问密钥，不面向公网部署。文件接口校验规范目录和 PDF 后缀，阻止跨目录或符号链接访问。CSV 文本做公式前缀防护，所有筛选值参数化绑定。

## 真实状态

- 已归档 110 份 PDF、1,888 页，110 份资料的 1,888 页均有原始提取和保守清洗文本；550 页有核验标记，人工核验通过资料数仍为 0。
- 检索为原文子串与英文关键词匹配，不是分词/BM25/向量检索。保守清洗已运行；切分未运行。
- 同一设备的不同来源、硬件变体与资料版本仍需人工核验；界面不推断兼容性。
- CHAT_API_KEY 为空时只查证据；配置后可显式选择生成，问题与证据会发送到相应服务。模型引用编号错误时隐藏回答。
- 界面没有数据库管理、自动修改来源资料或伪造任务状态的功能。

## 验证

`uv run --group collection pytest -q`；`npm --prefix frontend run build`。

端到端检查涵盖：浏览器查看真实统计 → 类别筛选 → 打开 PDF → 翻页 → 关键词检索 → 引用回到原件 → CSV 导出。远程聊天 API、PostgreSQL 和向量问答仍需配置后单独验证。
