# Render 只读展示部署

部署规格见根目录 render.yaml；服务 sentinel-security-rag，Docker，Free，Oregon，健康检查 /api/health。源码仍按 frontend/、backend/、pipelines/、database/ 分离。为降低配置成本，首版将编译后的前端和独立 API 放进同一容器，通过同域提供访问，未改成本地开发脚手架。

## 数据与权限

- database/snapshots/library.sqlite3.gz 是已核验总库的只读压缩快照，不含 PDF 或密钥；对应 JSON 记录压缩/解压哈希、处理批次、表计数。
- 生成：`uv run python -m pipelines.deployment.snapshot export`，会核对总库报告哈希和 110 份本地 PDF 哈希。新数据应先完成采集、清洗核验并重建总库，再导出快照。
- 构建镜像时恢复快照；已有不同数据库时拒绝覆盖。重启不依赖临时磁盘的历史写入。
- Docker 镜像不包含原始 PDF。缺少本地 PDF 时，仅在 REMOTE_PDF_ENABLED=true 的部署中按登记的官方 URL 读取。限制 HTTPS 厂商域名、逐跳重定向、大小与时间，检查 PDF 签名和采集时 SHA-256。官方文件变化时明确报错，不混入新版本。
- 原件最多 48 MiB 进程内缓存，重启后可丢弃；不写入 raw/，不改变原件或清单。
- 部署入口只注册资料查询接口，不暴露 /documents、/compatibility 等写入接口。模型生成强制关闭，CHAT_API_KEY 留空。PostgreSQL、切分和向量化尚未接入。

## 在 Render 开通

1. 登录 https://dashboard.render.com/ 。
2. 用 Blueprint 从公开仓库 https://github.com/CaptSteven/building-security-rag 读取根目录 render.yaml；确认只创建一个 Free Web Service，不创建付费数据库或磁盘。
3. 或选择 New → Web Service → Public Git Repository，填写仓库 URL，分支 main、语言 Docker、Dockerfile Path ./Dockerfile、实例 Free、健康检查 /api/health。其余环境变量按 render.yaml 设置。
4. 等待构建和部署成功，记录平台实际分配的 *.onrender.com URL，不能根据服务名猜测已经上线。
5. 验证 110 份 / 1,888 页统计、原始与清洗文本检索、PDF 原件页码定位、质量清单导出。测试官方原件不可访问时的错误提示。

首次部署需要 Render 账户。若出现新协议、验证码或信用卡验证，由账户所有人操作；不要升级付费方案绕过。免费服务闲置 15 分钟休眠、重新唤醒需等待。

## 本地生产入口验证

```bash
npm --prefix frontend ci
npm --prefix frontend run build
REMOTE_PDF_ENABLED=true uv run uvicorn security_rag.deployed_app:create_app --factory --host 127.0.0.1 --port 8010
# 完整容器验证（需要 Docker Hub/GHCR 网络可用）
docker build -t sentinel-security-rag:render .
docker run --rm -p 10000:10000 sentinel-security-rag:render
```

来源：[Docker 部署](https://render.com/docs/docker)、[Blueprint 配置](https://render.com/docs/blueprint-spec)、[免费限制](https://render.com/docs/free)。
