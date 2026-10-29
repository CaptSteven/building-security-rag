# 离线数据处理

- collection/：来源发现、下载、离线整理与核验。
- cleaning/：已实现全库提取、保守格式清洗、质量标记与核验后发布，见 cleaning/README.md。
- chunking/：后续正式切分模块，尚未实现。后端 service.py 中已有的原型切分函数不代表真实语料已完成切分。
- tests/：数据工程模块测试。

在项目根目录运行，输出严格遵循 data/README.md；不需要启动后端或数据库服务：

```bash
uv sync --group collection --group dev
# 仅在明确要重新采集时执行以下两步；新一轮请使用新 run_id：
uv run --group collection python -m pipelines.collection.discover_sources
uv run --group collection python -m pipelines.collection.collect_sample --run-id 新的运行编号
# 对已有资料进行离线核验，不下载新文件：
uv run --group collection python -m pipelines.collection.organize_sample --run-id security_sample_20261027T070841Z
```

先前执行的采集脚本与锁文件保存在 logs/collection/ 的历史快照中，不要当作当前入口运行。路径迁移映射在 logs/migrations/。当前 collection 依赖组与后端依赖分开声明在工作区配置中，前端依赖独立声明在 frontend/package.json。

## 批量扩充与总目录

批量采集入口按 SHA-256 对所有已登记批次去重，只计入可读取的官方参数表、手册和安装/接线资料。每次使用新 run_id，不覆盖历史批次；中断后可使用新 run_id 继续，已完成文件会从各轮清单重新识别。

```bash
uv run --group collection python -m pipelines.collection.bulk_collect --target-total 110
# 达到数量并结束采集后，核验全部批次并建立总目录：
uv run --group collection python -m pipelines.collection.build_library --minimum 100
```

总目录数据库：database/sqlite/library.sqlite3；总清单与统计：reports/library/。批量新增文件只登记原件和页数，extraction_status 为 not_started，不冒充已经提取、清洗或切分。清洗发布后，总库合并原始页文本、清洗页文本及处理批次记录；当前已覆盖 110 份、1,888 页。
