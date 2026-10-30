# 楼宇安保设备 RAG 知识库

当前阶段：官方资料小样本采集与整理。最新结果见 [本地资料库](../reports/datasets/security_sample_20261027T070841Z/README.md)。

已下载 9 份真实官方 PDF，覆盖四类设备，共 145 页；2 条视频因登录/人机验证未下载，另 1 份手册需手工获取，见资料库中的 MANUAL_ACTIONS.md。原件、来源快照、哈希、日志和 SQLite 目录已保存在本地。文本仅按页提取，尚未清洗、切分或向量化。

早期后端原型见下方。`backend/examples/demo-camera.json` 仍是虚构测试数据，不计入真实资料库。历史分步流程见 [数据处理流程](../docs/history/data-pipeline-20261021.md)。

## 架构

```mermaid
flowchart LR
  A[厂商手册 / 数据表 / 兼容清单] --> B[文本提取与人工审核]
  B --> C[关系表：品牌 / 型号 / 参数 / 协议 / 版本]
  B --> D[切片 → 独立 Embedding API]
  D --> E[pgvector 向量]
  Q[问题 + 显式筛选条件] --> C
  Q --> E
  C --> F[检索融合与来源证据]
  E --> F
  F --> G[DeepSeek 或兼容 Chat API]
  G --> H[回答 + 引用 + 原始证据]
```

向量和关系是两个逻辑底座，当前放在同一个 PostgreSQL 实例内，便于事务一致性。需要独立向量服务时再拆分。关系表不是 Neo4j 知识图谱。

聊天 API 与 Embedding API 独立配置。DeepSeek 接入采用官方的 OpenAI-compatible Chat 接口；不假设聊天服务同时提供向量接口。向量服务需支持 `POST /embeddings`，请求包含 `model,input`，响应包含 `data[index,embedding]`。

## 启动

需要 Python 3.11+、uv、已启动的 Docker 服务。所有命令在项目根目录 RAG/ 执行。

```bash
cp backend/.env.example backend/.env
uv sync --group dev
docker compose -f database/postgresql/compose.yaml up -d --wait
uv run python -m security_rag.cli init-db
uv run uvicorn security_rag.api:app --host 127.0.0.1 --port 8000
```

先在 `backend/.env` 填好向量服务的 `EMBEDDING_BASE_URL / EMBEDDING_MODEL / EMBEDDING_DIM / EMBEDDING_API_KEY`。维度必须与模型输出一致。聊天生成另填 `CHAT_API_KEY`；`CHAT_MODEL` 可替换为账号实际可用的模型。密钥只保存在本地 `backend/.env`，不要提交。

默认数据库端口为 `55432`，API 文档为 <http://127.0.0.1:8000/docs>。数据库及 API 默认绑定本机。默认数据库密码只用于本地开发；修改 `POSTGRES_PASSWORD` 时同步修改 `DATABASE_URL`。本原型的 `API_KEY` 是共享维护密钥，没有多用户角色或租户隔离，不适合直接公网部署。

## 入库和查询

配置好向量服务后：

```bash
uv run python -m security_rag.cli ingest backend/examples/demo-camera.json
curl -s http://127.0.0.1:8000/query -H 'Content-Type: application/json' --data-binary @backend/examples/query.json
```

如果设置了 `API_KEY`，所有数据接口及 curl 请求都要加 `X-API-Key`。上面示例用 `generate=false`，所以不需要聊天密钥，但 hybrid/vector 查询仍需要向量服务。

真实入库 JSON 参照 `backend/examples/demo-camera.json`，替换为有权使用的实际资料。新资料默认 `pending`，人工核验后改为 `verified` 再入库。默认检索排除 `pending/demo`；示例专门开启 `include_unverified`。

- `source_key` 标识一份确定的来源与版本；相同 key 重新入库会在单个事务中替换切片和元数据，清除其旧兼容关系。需要保留历史时使用新 key。
- 参数和协议挂在资料版本上，避免不同手册版本被无依据合并。`specs` 中单位应在字段名里统一，例如 `resolution_mp`、`power_w`、`temperature_min_c`。
- 文本型 PDF：`uv run python -m security_rag.cli ingest-pdf 手册.pdf 元数据.json`。元数据与入库 JSON 一致但省略 text/page。每页单独入库并保留页码。扫描件、复杂表格需先 OCR/版面解析；当前不自动处理图片与跨页表格。
- PDF 分页操作不是全文件事务，失败后可用相同 source_key 重试。PDF 页数减少不会自动删除旧尾页，应手工清理或采用新版本 key。

查询示例：

```json
{
  "question": "这款门禁支持什么协议，有哪些安装限制？",
  "filters": {
    "category": "门禁",
    "brand": "实际品牌",
    "model": "实际型号",
    "protocol": "OSDP",
    "spec_equals": {"poe": true}
  },
  "mode": "hybrid",
  "generate": true,
  "top_k": 6
}
```

`hybrid` 融合向量排名、原句/型号子串匹配和显式条件查询；`relational` 不调用向量服务；`vector` 只做向量排序。所有通道共用品牌、型号、类别、协议、参数及审核过滤条件。当前参数查询支持精确相等，不包含范围、单位换算、自动自然语言到 SQL。

中文匹配是子串匹配，不是 BM25。默认向量搜索是过滤后的精确搜索，索引已预留；规模扩大后需评估 HNSW 召回与过滤策略。原型未设置语义相关性阈值，因此近邻不一定相关；生产化前需用领域评测集校准。回答附原文和来源，引用编号错误时隐藏模型回答，但编号检查不能证明内容正确。

## 关系与兼容性

- `POST /devices/search`：参数、协议、品牌型号筛选，返回设备 ID 和各版本来源声明，最多 100 条。
- `POST /compatibility`：维护有方向的兼容性事实；包含 `source_device_id,target_device_id,document_id,verdict,conditions,evidence_quote`。结论为 `compatible/incompatible/conditional`。要求关联已核验资料，原文摘录需出现在资料片段中。维护者仍需核对资料是否确实覆盖这对型号。
- `GET /compatibility/{device_id}`：返回该型号相关兼容记录和来源；未记录表示未知。兼容关系暂不自动接入自然语言 `/query`，通过此专用接口查。

“都支持 ONVIF/OSDP”不等于“已验证兼容”。应记录主从方向、硬件版本、固件版本、功能范围和测试条件。

## 测试

```bash
uv run --group collection pytest -q
# 在独立测试数据库运行真实 SQL、向量检索及幂等替换测试：
RAG_TEST_DATABASE_URL=postgresql://rag:rag_local_only@127.0.0.1:55432/security_rag_test uv run --group collection pytest -q -m integration
```

集成测试的测试库要预先创建，仅允许专用测试库。测试向量在本地生成，不调用收费 API。未设置测试连接时集成用例自动跳过。

## 资料建设顺序

1. 每类先选少量常见品牌与型号，建立来源台账：官方产品页、手册、数据表、固件说明、兼容清单；保留 URL、下载时间、版本、页码和使用权限。
2. 先人工核验 30–50 个型号，统一型号别名、单位与字段。未提及参数记录为未知，不能补成“不支持”。
3. 建立至少 50–100 条真实问题及标准证据，覆盖精确型号、条件筛选、跨版本冲突、兼容性和资料不足拒答；评估 recall@k、引用正确率和错误兼容结论。
4. 验证后扩展 OCR、表格解析、结构化抽取审核、别名检索、范围条件、重排、资料更新任务和增量索引；再补用户权限、迁移、备份与监控。

详细领域字段和验收范围见 `../docs/domain.md`。

参考：[DeepSeek 官方接口](https://api-docs.deepseek.com/)；[pgvector 官方项目](https://github.com/pgvector/pgvector)。

## DeepSeek 会话 API

新增 POST /api/library/ask 和 POST /api/library/deepseek/check，通过 X-DeepSeek-Key 使用用户自己的官方 Key。完整请求、响应、限流及脱敏记录约定见 docs/deepseek-api.md。原有本地 CHAT_* 环境配置保留；线上 /ask 不回退到服务器公共 Key。
