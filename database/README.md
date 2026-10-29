# 数据库独立目录

- sqlite/<run_id>/catalog.sqlite3：已生成的本地资料目录库，包含 devices / assets / pages；文件路径相对项目根目录。SQL 定义在 sqlite/schema.sql。
- postgresql/：RAG 后端的 PostgreSQL + pgvector 服务配置与 SQL 定义。当前未完成服务端端到端验证。
- backups/：数据库备份预留目录。

数据库持久化与应用代码分离。PostgreSQL 数据由 Docker 命名卷 rag_rag_db 持久化，不写进 backend/src。当前向量和关系表仍在同一 PostgreSQL 实例内，本次只整理目录，没有拆成两个数据库实例。

在项目根目录启动（不是本次重构必须执行的步骤）：

```bash
docker compose -f database/postgresql/compose.yaml up -d --wait
uv run python -m security_rag.cli init-db
```

schema.sql 包含 __EMBEDDING_DIM__ 占位符，由初始化命令根据配置替换，不能直接作为普通 SQL 文件执行。初始化 SQL 当前幂等，不是已建立版本迁移系统。不要将已有 SQLite 目录误当作已向量化的 RAG 数据库。

## 跨批次总目录

`library.sqlite3` 使用 `library_schema.sql`，按 `(run_id, asset_id)` 区分不同批次的同名资料编号；`downloaded_pdfs` 视图只包含成功下载的 PDF。每轮独立的 `sqlite/<run_id>/catalog.sqlite3` 仍保留，不被总目录替代或覆盖。

```sql
SELECT count(DISTINCT sha256) FROM downloaded_pdfs;
SELECT category,count(DISTINCT sha256) FROM downloaded_pdfs GROUP BY category;
```

只有原件哈希、PDF 可读性与外键核验通过后，离线汇总脚本才会用临时库原子替换总目录。统计 PDF 数量不等于统计产品型号数量。

## 文本处理追溯

总库 pages 保留原始提取文本；cleaned_pages 保存保守清洗文本，通过 (run_id, asset_id, page) 关联，记录原始/清洗文本哈希、PDF 哈希、处理批次与质量标记。processing_runs 记录规则版本、处理清单路径/哈希及统计。当前两层各 1,888 页，向量索引仍未建立。

```sql
SELECT count(*) FROM pages;
SELECT count(*) FROM cleaned_pages;
SELECT processing_run_id,rules_version FROM processing_runs;
```

本轮发布前的总库、批次目录库和来源清单备份位于 logs/processing/cleaning_20261027T084605Z/before-publish/；历史备份不随当前库更新。
