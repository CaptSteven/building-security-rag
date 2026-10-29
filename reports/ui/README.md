# 前后端验证记录

入口：`uv run python backend/dev.py`。浏览器地址 http://127.0.0.1:5173/。

已验证浏览器 → Vite 代理 → FastAPI → 只读 SQLite / 原件 → 界面：110 份资料统计、门禁 26 份筛选、PDF 渲染与翻页、PoE 6 条证据检索、引用跳转到原件第 4 页、CSV 110 条记录导出。开发启动器可启动两端，Ctrl+C 同时停止。

前端生产构建通过；21 项测试通过，1 项 PostgreSQL 集成测试因测试数据库未配置而跳过。刷新并重新启动后，无浏览器错误或警告。开发期间变更 Hook 依赖时曾产生一次热更新警告，重新加载后消失；最终代码无此运行时警告。

原始 110 份 PDF 哈希均未改变。远程聊天 API、PostgreSQL 向量库及语料清洗切分尚未运行，不能作为已完成的验证。

- [桌面总览](overview-desktop.png)
- [桌面资料列表](documents-desktop.png)
- [移动布局](overview-mobile.png)
- [机器可读核验记录](verification.json)
