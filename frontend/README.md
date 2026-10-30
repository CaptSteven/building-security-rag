# 前端应用

React + TypeScript + Vite，使用独立 package.json / package-lock.json。图标由 lucide-react 提供，PDF.js 按需加载并在浏览器本地渲染原件，不依赖浏览器内置 PDF 插件或外部 CDN。

在项目根目录：

```bash
npm --prefix frontend ci
npm --prefix frontend run dev
# 构建及类型检查：
npm --prefix frontend run build
```

开发服务为 http://127.0.0.1:5173/，/api 经 Vite 代理到独立后端 http://127.0.0.1:8000。后端需同时启动。也可执行 `uv run python backend/dev.py` 同时启动两端；Ctrl+C 关闭两端。

页面：知识总览、设备资料库、检索与问答、数据处理状态、连接与设置。筛选、分页、CSV 导出、PDF 预览和翻页、原始文件下载及来源追溯均使用真实后端接口。

前端不读取 data/，不连接数据库，不持久存储 API 密钥。若后端设置 API_KEY，在连接页面输入会话访问密钥；它仅保存在当前页面内存中，刷新后清除。模型密钥仅由后端环境变量管理。

当前可选择检索全部 110 份资料的 1,888 页原始提取文本或保守清洗文本；不把关键词查询称为向量检索。聊天服务未配置时生成开关禁用；启用后会把用户问题和证据发给配置的聊天 API。PDF 引用点击后定位到对应页。

数据处理页展示真实清洗批次、规则、质量标记、原件定位与核验清单导出；批量处理通过离线命令执行。保守清洗已完成，人工核验、切分与向量化未完成。

DeepSeek：连接设置支持会话 Key 输入、模型选择、官方模型列表检查和清除。/ask 附带 X-DeepSeek-Key，仅发送到本项目同域后端；不写浏览器持久存储。问答支持有引用回答、错误时保留证据、调用信息及 JSON 导出；详见 docs/deepseek-api.md。
