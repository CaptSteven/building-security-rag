# 免费网站部署方案（2026-10-29）

仓库已改为公开：https://github.com/CaptSteven/building-security-rag 。本次完成可见性修改及方案调研，尚未创建云服务或发布网站。额度和限制按下列官方文档查询时的内容记录，实际开通时以控制台为准。

## 推荐：Render 前后端分开部署，数据库按阶段接入

| 层 | 服务 | 免费范围与主要限制 |
|---|---|---|
| React 前端 | Render Static Site | 免费静态托管，支持 Git 自动部署、HTTPS 和平台域名；仍受流量、构建额度约束 |
| FastAPI 后端 | Render Free Web Service | 750 实例小时/月/工作区；15 分钟无访问休眠，唤醒约 1 分钟；没有免费持久磁盘 |
| 关系和向量数据库（后续） | Neon Free PostgreSQL + pgvector | 当前免费档每项目 1 GB 存储、100 CU-hours/月；闲置计算可暂停；不要求信用卡。索引、表和向量合计占用存储，需实际测量 |

来源：[Render 静态托管](https://render.com/docs/static-sites)、[Render 免费限制](https://render.com/docs/free)、[Neon 价格](https://neon.com/pricing)、[Neon pgvector](https://neon.com/docs/extensions/pgvector)。

这是基于当前 React + FastAPI 技术栈的适配判断，不是已完成云端验证。Render 前端与后端分别为独立服务，源码和数据库目录继续分开。

第一阶段可先部署只读的资料浏览、关键词检索与处理追溯。当前功能使用 SQLite，不需要为了演示立即开通 Neon；需生成专门的可重建只读部署快照，随构建恢复，不能把运行中的写入放在 Render 临时磁盘。第二阶段完成正式切分、向量化后，再将关系与向量数据接入 Neon。

## 当前项目上线前的必要适配

1. **目录数据**：GitHub 没有 SQLite 数据库，现有 build_library 又会核验本地 PDF。不能直接在云端原样启动。需要从已核验的输入生成带哈希的部署快照，或提供完整原件后重建总库；明确展示数据版本，不能伪造来源。
2. **PDF 原件**：110 份约 299 MB 原件目前仅在本地。可先让线上版打开官方来源，但这不能替代当前页面内 PDF 预览。若保留页码定位和原件预览，需要独立对象存储及后端文件读取适配。
3. **前后端 API**：当前浏览器请求固定为 /api/library，Vite 开发代理仅在本机开发时存在。生产环境需要同域反向代理，或可配置 API 基址并设置受限 CORS；文件下载和 CSV 请求也需一起适配。
4. **启动与健康检查**：后端应监听 0.0.0.0 和平台 PORT；使用 /api/health 检查 API 进程，不能使用依赖尚未配置 PostgreSQL 的 /health。前端构建命令 npm ci && npm run build，目录 frontend，产物 dist。
5. **模型**：DeepSeek 和向量化 API 的调用费用独立于免费托管。没有模型配置时继续提供关键词证据检索。密钥仅保存在后端环境变量，启用公开模型调用前落实访问控制、调用额度及速率限制。
6. **答辩验证**：检查冷启动、真实统计、两层文本检索、PDF 定位、质量清单导出；当前资料仍未切分或向量化，不能把上线当作完整 RAG 已实现。

Render 临时磁盘在重启、重新部署和休眠时可能丢失运行时改动。不要把待人工核验记录或上传资料只保存在该磁盘。Render 的免费 PostgreSQL 30 天到期，不适合长期答辩资料存储。

## PDF 存储选项

Cloudflare R2 Standard 提供每月 10 GB-month 免费存储额度，另有请求额度，出站流量不收费；当前约 299 MB 原件在存储容量额度内。它是带免费额度的计量服务，不能据此承诺所有使用都永久免费。开通账户、计费要求、请求和下载流量模式要另行核对；本次没有创建桶或上传原件。

[官方价格](https://developers.cloudflare.com/r2/pricing/) · [开通入口](https://developers.cloudflare.com/r2/get-started/)。如只做第一阶段演示，可暂不引入第三个平台，以官方来源链接替代线上原件读取，但必须在界面明确说明。

## 替代方案

- **Cloudflare Pages 前端 + Render 后端**：前端免费计划当前每月 500 次构建、20,000 文件，单文件 25 MiB。多一个平台，需要处理 API 路由或跨域配置。[限制](https://developers.cloudflare.com/pages/platform/limits/)
- **GitHub Pages 前端 + 独立后端**：公开仓库可用免费静态托管，但无法独立运行 Python 后端；还需要配置仓库子路径与 API。[官方说明](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)
- **Hugging Face Spaces**：当前官方说明 Static Spaces 免费；新建 Docker/Gradio 计算型 Space 需要付费计划，免费账户的部分 ZeroGPU Gradio 资格不等同于当前 FastAPI Docker 应用的通用免费托管，因此不作为本项目默认免费方案。[官方说明](https://huggingface.co/docs/hub/spaces-overview)

## 开通网址与顺序

1. https://dashboard.render.com/ ：使用 GitHub 连接项目，创建 Static Site 与 Free Web Service。先完成上述数据和路由适配，再实际发布。
2. https://console.neon.tech/ ：正式进入关系/向量入库阶段时开通 Free 项目。
3. PDF 在线预览确定保留时，再配置对象存储。

尚未登录或开通这些服务，未接受新平台协议，未产生托管资源费用。公开 GitHub 仓库不代表已授予第三方厂商文档再许可；代码和处理产物的来源说明继续保留。

## 实施进度补充（2026-10-29）

已新增 render.yaml、Dockerfile、校验后的只读 SQLite 压缩快照及官方 PDF 哈希校验读取。首版采用一个免费 Docker 服务提供同域前端/API，源码继续分离。实际云端部署仍待 Render 账号登录和平台构建验证；最新说明见 render-deployment.md。
