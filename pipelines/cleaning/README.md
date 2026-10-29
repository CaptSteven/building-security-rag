# 逐页提取与保守清洗

在项目根目录执行；不需要模型密钥或 PostgreSQL。

```bash
# 生成新的处理批次（每次运行独立保存，终端输出 run_id）
uv run --group collection python -m pipelines.cleaning.process_library run
# 阅读新批次 reports/processing/<run_id>/README.md 与 quality.csv 后发布
uv run --group collection python -m pipelines.cleaning.process_library publish --run-id <run_id>
```

本次已发布 cleaning_20261027T084605Z，勿对同一批次重复发布。publish 会核验原件和产物哈希、逐页重放清洗规则和行级映射，备份来源清单、批次库和总库，再更新当前目录；已有非空备份时拒绝覆盖。

输入为已登记的 PDF 原件；pypdf 逐页提取到 data/interim/extracted/<run_id>/v1/，未清洗。清洗文本与 *.map.jsonl 单独保存到 data/processed/cleaned/<run_id>/。规则、输入快照、处理清单与 publication.json 在 data/metadata/processing/<run_id>/；日志和执行代码快照在 logs/processing/<run_id>/。旧产物保留。

规则 conservative-whitespace-v1 只规范换行、BOM、控制字符和空白，不拼词、不补参数、不重排表格、不删除页眉页脚或页面、不做 OCR。每页保留来源 ID、页码、PDF 与文本哈希；映射为行级 Unicode 字符偏移（右端不含），不声称逐字符一一对应。

质量标记包括空白/图片页候选、稀疏文本、疑似黏词、短行碎片、替换字符、密集数字布局。标记可重叠，仅用于安排核验，不能当作错误数量。自动清洗不等于人工事实审核。

JSONL 必须按文件物理换行读取，使用 pipelines.jsonl.read_jsonl；不可用 str.splitlines()，因为合法 JSON 字符串可能包含 U+2028/U+2029/U+0085。相关回归测试覆盖这一情况。
