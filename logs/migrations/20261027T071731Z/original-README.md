# 楼宇安保设备官方资料小样本

采集日期：2026-10-27（America/Los_Angeles）。这是本地原始资料库，尚未接入向量数据库或模型。

已下载 9 份文件，4 个设备目录，提取 145 页文本；视频已下载数量为 0。

## 已下载文件

| 编号 | 设备 | 类型 | 页数 | 本地原件 | 官方来源页 |
|---|---|---|---:|---|---|
| A001 | axis-m2035-le | datasheet | 5 | [PDF](raw/A001_axis-m2035-le_datasheet.pdf) | [来源](https://www.axis.com/products/axis-m2035-le/support) |
| A002 | axis-m2035-le | installation | 36 | [PDF](raw/A002_axis-m2035-le_installation.pdf) | [来源](https://www.axis.com/products/axis-m2035-le/support) |
| A004 | axis-a1210 | datasheet | 6 | [PDF](raw/A004_axis-a1210_datasheet.pdf) | [来源](https://www.axis.com/products/axis-a1210/support) |
| A005 | axis-a1210 | wiring | 14 | [PDF](raw/A005_axis-a1210_wiring.pdf) | [来源](https://www.axis.com/products/axis-a1210/support) |
| A006 | axis-a1210 | installation | 42 | [PDF](raw/A006_axis-a1210_installation.pdf) | [来源](https://www.axis.com/products/axis-a1210/support) |
| A007 | axis-a1210 | comparison | 1 | [PDF](raw/A007_axis-a1210_comparison.pdf) | [来源](https://www.axis.com/products/axis-a1210/support) |
| A008 | axis-i8116-e | datasheet | 7 | [PDF](raw/A008_axis-i8116-e_datasheet.pdf) | [来源](https://www.axis.com/products/axis-i8116-e/support) |
| A009 | axis-i8116-e | installation | 32 | [PDF](raw/A009_axis-i8116-e_installation.pdf) | [来源](https://www.axis.com/products/axis-i8116-e/support) |
| A011 | optex-flx-p-dt | datasheet | 2 | [PDF](raw/A011_optex-flx-p-dt_datasheet.pdf) | [来源](https://www.optex-europe.com/products/intrusion-detection/flx-p-dt-flipx-professional-indoor-pir-with-dual-technology-) |

## 目录说明

- raw/：厂商原始 PDF，不改写、不翻译。
- sources/：官方页面快照、采集元数据、robots.txt。初始来源发现发生在采集前，时间见各 JSON；不是站点全量快照。
- pages/：首轮按页提取文本；部分文档出现 fontTools 缺失提示，因此只作历史记录。
- pages_v2/：安装 fontTools 后重新提取的文本。保留页码与原件哈希，未做清洗或语义审核。
- manifest.json / manifest.csv：来源、文件状态、大小、SHA-256、页数、获取时间、提取版本。
- catalog.sqlite3：devices、assets、pages 三张表；assets 中包括失败/待人工记录，查询成功文件须筛选 status。
- logs/：HTTP 状态、工具命令、失败原因和代码/依赖快照。视频没有保存账号或 cookies。
- previews/：每份 PDF 的第一页预览，供检查是否下载到正确文档；不等于逐页人工核验。

## 范围与核验边界

AXIS M2035-LE、A1210、I8116-E；OPTEX FLX-P-DT。选取理由：四类设备各一例，官方来源、小样本可追溯；不是市场代表性抽样。
安装指南可能是系列共用文档；OPTEX 手册还涉及 X5/X8/X9 等变体，不能默认所有子型号参数一致。参数没有自动抽取到 devices 表中。
入侵探测器产品页存在标题型号与概述段型号不完全一致的情况，保留原始页面，不据此自动纠正产品参数。
下载成功只表示文件可读取及哈希一致；未验证全部参数、表格提取顺序或兼容性，也未进行实验评测。
来源均保留厂商版权；未对再分发许可作判断。本轮不把原件发布到公网。

## 重现

在项目根目录执行。每次采集指定新的输出目录，避免覆盖旧证据。
```bash
uv sync --group collection
uv run --group collection python scripts/discover_sources.py > research/catalog/discovery.txt
uv run --group collection python scripts/collect_sample.py --output research/datasets/新的运行目录
uv run --group collection python scripts/organize_sample.py research/datasets/新的运行目录
```

```sql
SELECT d.category,d.brand,d.model,a.kind,a.path FROM assets a JOIN devices d USING(device_id) WHERE a.status='downloaded';
SELECT asset_id,page,substr(text,1,250) FROM pages WHERE text LIKE '%PoE%' LIMIT 10;
```

说明：网页和文件会更新，重现命令用于重新获取和比较；内容一致性应以历史快照及哈希判断，不承诺将来相同 URL 内容不变。

待人工项目见 [MANUAL_ACTIONS.md](MANUAL_ACTIONS.md)。
