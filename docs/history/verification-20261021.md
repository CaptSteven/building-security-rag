# 验证记录

2026-10-21（America/Los_Angeles）

- `uv sync --group dev` 成功，依赖版本保存在 uv.lock。
- `uv run pytest -q`：14 passed，1 skipped；跳过的是需要专用 PostgreSQL 数据库的集成测试。
- `uv run python -m compileall -q security_rag` 成功。
- `docker compose config --quiet` 成功。
- HTTP MockTransport 验证了 embeddings/chat 请求路径、认证、响应解析；这些不代表真实外部服务已连通。
- 启动了原有 Colima 实例。`docker compose up -d --wait` 拉取镜像失败：Docker VM 使用 `[::1]:53` 解析 registry-1.docker.io，收到 connection refused。未修改用户的容器 DNS 配置。
- PostgreSQL 真实 SQL、向量排序、替换事务及兼容性外键尚未完成运行验证。
- 未配置或调用真实模型 API；未导入真实品牌产品数据。
- 测试运行有一项 Starlette 对 httpx TestClient 的弃用提示，不影响当前通过结果。

继续：修复本机 Docker DNS 后启动 compose；填写模型配置；初始化数据库；创建独立测试库并运行集成测试；再导入第一批经过核验的官方资料。
