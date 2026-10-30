# 楼宇安保设备 RAG 知识库

前端、后端、离线数据处理、数据库及数据文件分开管理。现有 110 份经 SHA-256 去重的官方 PDF，覆盖四类设备，共 1,888 页，约 299 MB。110 份 PDF 的 1,888 页均已提取并完成保守格式清洗；186 页发生格式变化，550 页有自动核验标记（涉及 66 份资料）。人工核验尚未完成，未切分或向量化。独立前端已实现，支持资料浏览、PDF 预览、来源追溯和关键词证据检索。

```text
RAG/
├── frontend/                    # React / TypeScript / Vite 前端
├── backend/                     # 后端独立 Python 包、配置示例、测试及虚构样例
│   ├── src/security_rag/
│   ├── tests/
│   ├── examples/
│   ├── .env.example
│   └── pyproject.toml
├── pipelines/                   # 离线数据工程
│   ├── collection/               # 已实现的采集与离线核验
│   ├── cleaning/                 # 已实现：逐页提取、保守清洗与追溯
│   ├── chunking/                 # 待实现
│   └── tests/
├── database/
│   ├── postgresql/               # 服务配置与关系/向量表 SQL
│   ├── sqlite/                   # 资料目录数据库及 SQL
│   └── backups/
├── data/
│   ├── raw/
│   │   ├── pdfs/                 # 清洗切分前的 PDF 原件，独立存放
│   │   ├── videos/               # 当前无成功下载的视频
│   │   └── webpages/             # 官方网页与 robots.txt 快照
│   ├── metadata/                 # 清单与来源描述
│   ├── interim/extracted/        # 未清洗的逐页提取文本
│   ├── processed/cleaned/        # 清洗文本与逐行映射
│   ├── processed/chunks/         # 切分输出，当前为空
│   └── inbox/                    # 人工下载待登记文件
├── logs/                        # 采集日志与目录迁移审计
├── reports/                     # 资料目录、核验报告、预览及人工处理清单
├── docs/                        # 工程规范、领域说明、历史过程
├── pyproject.toml               # 工作区与数据工程/测试依赖
└── uv.lock                      # 工作区统一依赖锁
```

各数据层以 run_id 隔离；PDF 再按类别、设备分类。规范见 [目录约定](docs/project-structure.md)。

## 资料入口

- [资料目录和文件链接](reports/library/README.md)
- [清洗切分前的 PDF 原件](data/raw/pdfs/)
- [SQLite 资料目录库](database/sqlite/library.sqlite3)
- [资料清单](reports/library/catalog.json)
- [未成功下载与待人工处理清单](reports/library/MANUAL_ACTIONS.md)

interim/extracted/ 保留未清洗的逐页提取文本；processed/cleaned/ 保存单独的格式清洗结果。历史提取版本仍保留。backend/examples/ 是虚构测试资料，不能混入真实语料。原始 PDF 不得覆盖或原地清洗。

## 前后端工作台

```bash
uv sync --group collection --group dev
npm --prefix frontend ci
uv run python backend/dev.py
```

打开 http://127.0.0.1:5173/；Ctrl+C 同时停止两端。浏览与关键词检索不依赖 PostgreSQL 或模型密钥。

[前后端说明与 API](docs/frontend-backend.md) · [前端说明](frontend/README.md)

## 离线数据工程

以下命令均在项目根目录执行。离线核验不需要模型密钥或数据库服务。

```bash
uv sync --group collection --group dev
uv run --group collection python -m pipelines.collection.organize_sample --run-id security_sample_20261027T070841Z
uv run --group collection pytest -q
```

后端：

```bash
cp backend/.env.example backend/.env
# 仅使用 PostgreSQL RAG 服务时执行：
docker compose -f database/postgresql/compose.yaml up -d --wait
uv run python -m security_rag.cli init-db
uv run uvicorn security_rag.api:app --host 127.0.0.1 --port 8000
```

[后端说明](backend/README.md) · [离线采集入口](pipelines/README.md) · [数据库说明](database/README.md) · [数据分层规范](data/README.md)

最新批次已完成官方 PDF 扩充；此前目录迁移记录保留在 logs/migrations/。前后端工作台已接入本地资料目录，模型与向量服务尚未就绪。关系/向量仍共享同一 PostgreSQL 实例。SQLite 资料目录可离线使用；PostgreSQL 端到端集成验证仍待完成。

本轮清洗：[处理报告](reports/processing/cleaning_20261027T084605Z/README.md) · [清洗操作说明](pipelines/cleaning/README.md)。

## GitHub 仓库

代码与处理记录保存于公开仓库 [CaptSteven/building-security-rag](https://github.com/CaptSteven/building-security-rag)。PDF 原件、SQLite 数据库及密钥保留本地；克隆后需先恢复原件并重建目录库，详见 [上传范围与恢复步骤](docs/github.md)。GitHub 上传不代表在线服务已部署。

免费托管方案与上线前需要完成的适配，见 [部署方案调研（2026-10-29）](docs/free-deployment.md)。

Render 只读展示部署：[配置与数据恢复说明](docs/render-deployment.md)，使用根目录 render.yaml 和 Dockerfile。云端是否上线以 Render 实际部署状态为准。

## 在线演示

[打开 Sentinel 安保资料工作台](https://sentinel-security-rag.onrender.com/)（Render Free）。已上线资料目录、逐页关键词检索、质量追溯与原件预览；向量检索尚未开放；DeepSeek 问答可使用自己的会话 Key 启用。免费实例闲置后会休眠，首次访问需等待唤醒。云端验证记录见 reports/deployment/render_20261029/cloud-verification.json。

DeepSeek 直接接入：[网页操作、API 请求与验证范围](docs/deepseek-api.md)。Key 只在本次页面会话中保留，生成按本人账户实际用量计费。
