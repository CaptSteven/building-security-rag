# GitHub 仓库与本地资料

仓库： https://github.com/CaptSteven/building-security-rag 。2026-10-28 创建为私有仓库；2026-10-29 按用户要求改为公开仓库。

GitHub 保存前后端源码、离线处理脚本、SQL、依赖锁、资料来源清单、处理规则及审计报告。上传仓库不等于已部署在线服务；前端、FastAPI 和 PostgreSQL 仍按本地说明启动。

## 上传范围

依照 .gitignore，以下内容只保留在本机：PDF/视频原件、SQLite 文件及数据库备份、.env 密钥、依赖目录和构建缓存。提取文本、清洗文本、映射及处理元数据随代码版本管理；这些资料来自官方文档，并非本项目原创。当前不声明对第三方资料的再许可。

本地 110 份原始 PDF 与三个 SQLite 库没有删除或移动。当前版本克隆到另一台机器后，不能直接浏览原件或使用完整目录服务，需要先恢复数据。

## 在另一台机器恢复

1. 克隆仓库并安装依赖：

```bash
git clone https://github.com/CaptSteven/building-security-rag.git
cd building-security-rag
uv sync --group collection --group dev
npm --prefix frontend ci
```

2. 从原工作区另行复制 data/raw/pdfs/ 到克隆目录下的相同路径。当前清单使用根目录相对路径；不要覆盖、修改或重命名 PDF。来源和预期 SHA-256 见 reports/library/catalog.json。无需将 .env 或本地密钥随数据复制。

3. 在克隆根目录校验原件并重建总库：

```bash
uv run --group collection python -m pipelines.collection.build_library --minimum 100
uv run --group collection pytest -q
npm --prefix frontend run build
uv run python backend/dev.py
```

构建脚本读取已登记的原件及文本产物，校验哈希后写入 database/sqlite/library.sqlite3。缺少原件时不要伪造文件或改写清单；先完成复制。历史每批次的 catalog.sqlite3 如需完整恢复，可另行从原工作区 database/sqlite/ 复制；总库重建不依赖它们。

4. 打开 http://127.0.0.1:5173/。PostgreSQL、向量索引和远程模型需按 backend/README.md 单独配置；当前语料尚未切分或向量化。

## 后续提交

```bash
git status --short
git add <明确需要提交的路径>
git diff --cached --stat
git commit -m "说明本次修改"
git push
```

不要强制加入已忽略的密钥、原件或数据库，也不要把历史 logs/ 快照当作当前脚本执行。
