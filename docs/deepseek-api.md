# DeepSeek 直接接入（2026-10-29）

## 网页使用

1. 打开 https://sentinel-security-rag.onrender.com/#settings 。
2. 在“直接使用 DeepSeek”填写自己的官方 API Key，选择 Flash 或 V4 Pro，点击“应用 Key”。
3. 可点“检查连接”：后端只调用官方 GET /models，不发起文本生成；连通不代表余额充足。
4. 进入“检索与问答”，输入型号和问题，勾选“生成回答”。先查本地资料，再将问题与最多 6 条页内证据发给官方 API。例：`Does A1210 support PoE?`。
5. 点击“导出本次记录”保存问题、证据、模型回答（如有）、引用、调用编号、时长与 token 用量，不包含会话 Key。
6. 使用完可清除会话 Key；刷新页面也会清除。密钥请在网站输入，不要发到聊天、GitHub issue 或提交进仓库。

网页持有的 Key 只在当前页面内存中保留。它会通过 HTTPS 交给本项目后端，再用于访问固定的 https://api.deepseek.com；不写入 localStorage/sessionStorage、业务数据库、应用审计日志或导出记录。应用代码无法替第三方浏览器扩展、用户自行配置的抓包/反向代理作保密保证。使用时应理解网站后端会处理本次 Key 与证据。

## 接口

所有接口沿用项目可选的 X-API-Key 访问认证；DeepSeek Key 使用独立 X-DeepSeek-Key 请求头。生产版本不提供任意上游 URL 或模型名输入。

| 接口 | 请求 | 行为 |
|---|---|---|
| POST /api/library/deepseek/check | X-DeepSeek-Key | 读取官方模型列表，返回支持的模型 ID；不生成文本 |
| POST /api/library/ask | X-DeepSeek-Key + 下方 JSON | 真实页文本检索、官方生成、引用编号校验 |
| POST /api/library/search | 原有请求 | 保留不依赖模型的关键词检索；生产版仍禁止通过 generate=true 使用服务器公共密钥 |

```json
{
  "question": "Does A1210 support PoE?",
  "category": "门禁",
  "text_source": "cleaned",
  "top_k": 6,
  "model": "deepseek-flash"
}
```

模型支持 deepseek-flash 与 deepseek-v4-pro，默认 Flash。新 /ask 固定调用官方 POST /chat/completions，stream=false、thinking disabled、max_tokens=1024，不做自动重试。聊天输出限制与引用验证不代表回答事实已经正确。

响应保持 evidence / answer / warnings，并增加 generation：request_id、provider、model、status、usage、cited_sources、duration_ms、error_code。status 可为 completed / failed / no_evidence。未检索到证据时不调用生成 API；密钥格式合法性校验仍先执行，但这不代表密钥已被上游验证。

失败时保留 evidence，answer 为 null，warnings 给出脱敏原因。覆盖无效 Key、余额不足、限流、超时、错误响应、引用缺失或无效、输出截断。不要把 HTTP 200 当作生成完成，应检查 generation.status。缺少 Key 返回 401，本服务限流返回 429。

## Python 直接调用

```python
from getpass import getpass
import httpx

key = getpass("DeepSeek API Key（不会回显）: ")
response = httpx.post(
    "https://sentinel-security-rag.onrender.com/api/library/ask",
    headers={"X-DeepSeek-Key": key},
    json={"question": "Does A1210 support PoE?", "text_source": "cleaned", "model": "deepseek-flash"},
    timeout=90,
)
response.raise_for_status()
result = response.json()
print(result.get("generation"), result.get("answer"), result.get("warnings"))
```

## 成本、限流与追溯

- 本轮实现每 Key 每分钟最多 6 次官方请求、进程内最多 2 个并发请求；检查连接也计入。只保存 Key 的 SHA-256 摘要与时刻，不记录明文。
- 这些是单进程的资源保护，重启会清空；不是跨实例账单上限。计费以 DeepSeek 账户为准，输入 token 也可能计费。
- 每次最多 6 条证据、每条最多 1,300 字符，输出最多 1,024 tokens。Render 免费实例休眠与上游超时都可能影响首次请求，不自动重试以避免重复消费。
- 应用审计仅记录调用编号、模型、状态、token 数、耗时及证据的批次/资料 ID、页码、PDF 哈希；不记录 Key、问题或生成原文。导出记录由用户主动保存。
- 检索优化为完整型号词优先于型号前缀，再比较关键词命中数。A1210 与 A1210-B 仍作为不同档案，不自动合并事实或兼容性。
- 当前是真实页文本的关键词检索增强问答，尚未做正式语料切分或向量化，不把新 API 描述成已完成的向量 RAG。

## 验证范围

测试使用明确隔离的虚构证据和 MockTransport；另以真实 A1210 资料检索、模拟生成进行接口集成验证。没有收到真实用户 Key，因此没有进行付费生成，不能声称已验证真实余额或真实回答质量。部署后可先检查不带 Key 返回 401、连接入口与型号排序，再由用户输入自己的 Key 做实际验收。

官方依据：[首个调用及模型名](https://api-docs.deepseek.com/)、[聊天参数](https://api-docs.deepseek.com/api/create-chat-completion/)、[模型列表](https://api-docs.deepseek.com/api/list-models/)、[错误码](https://api-docs.deepseek.com/quick_start/error_codes/)。
