# 官方资料小型数据库

运行编号：`security_sample_20261027T070841Z`。目录规范版本：2。
已下载 9 份文件，包含 4 个设备目录，共 145 页提取文本。待人工项目 3 个。

## 已下载资料

| 编号 | 设备 | 类型 | 页数 | 原始文件 |
|---|---|---|---:|---|
| A001 | axis-m2035-le | datasheet | 5 | [原件](../../../data/raw/pdfs/security_sample_20261027T070841Z/video_surveillance/axis-m2035-le/A001_axis-m2035-le_datasheet.pdf) |
| A002 | axis-m2035-le | installation | 36 | [原件](../../../data/raw/pdfs/security_sample_20261027T070841Z/video_surveillance/axis-m2035-le/A002_axis-m2035-le_installation.pdf) |
| A004 | axis-a1210 | datasheet | 6 | [原件](../../../data/raw/pdfs/security_sample_20261027T070841Z/access_control/axis-a1210/A004_axis-a1210_datasheet.pdf) |
| A005 | axis-a1210 | wiring | 14 | [原件](../../../data/raw/pdfs/security_sample_20261027T070841Z/access_control/axis-a1210/A005_axis-a1210_wiring.pdf) |
| A006 | axis-a1210 | installation | 42 | [原件](../../../data/raw/pdfs/security_sample_20261027T070841Z/access_control/axis-a1210/A006_axis-a1210_installation.pdf) |
| A007 | axis-a1210 | comparison | 1 | [原件](../../../data/raw/pdfs/security_sample_20261027T070841Z/access_control/axis-a1210/A007_axis-a1210_comparison.pdf) |
| A008 | axis-i8116-e | datasheet | 7 | [原件](../../../data/raw/pdfs/security_sample_20261027T070841Z/intercom/axis-i8116-e/A008_axis-i8116-e_datasheet.pdf) |
| A009 | axis-i8116-e | installation | 32 | [原件](../../../data/raw/pdfs/security_sample_20261027T070841Z/intercom/axis-i8116-e/A009_axis-i8116-e_installation.pdf) |
| A011 | optex-flx-p-dt | datasheet | 2 | [原件](../../../data/raw/pdfs/security_sample_20261027T070841Z/intrusion_alarm/optex-flx-p-dt/A011_optex-flx-p-dt_datasheet.pdf) |

## 数据分层

- [原始 PDF 文件夹](../../../data/raw/pdfs/security_sample_20261027T070841Z/)：下载原件，清洗及切分前的文件独立存放。
- [原始视频目录](../../../data/raw/videos/security_sample_20261027T070841Z/)：目前无成功下载的视频。
- [SQLite 资料目录数据库](../../../database/sqlite/security_sample_20261027T070841Z/catalog.sqlite3)：设备、文件状态、逐页提取文本。
- [完整清单 JSON](../../../data/metadata/runs/security_sample_20261027T070841Z/manifest.json) / [CSV](../../../data/metadata/runs/security_sample_20261027T070841Z/manifest.csv)：所有文件路径以项目根目录为基准。
- [来源快照](../../../data/raw/webpages/security_sample_20261027T070841Z/) 与 [原始日志](../../../logs/collection/security_sample_20261027T070841Z/)。
- [第一页预览](../../previews/security_sample_20261027T070841Z/contact-sheet.jpg)：已核对封面；不代表逐页语义审核。

## 尚未完成的内容

文本仅按页提取，未清洗、未切分、未向量化；数据条目没有被标为人工核验通过。v1 是首轮历史提取，v2 是补充 fontTools 后的重新提取；两版都属于未清洗文本。
文件中可能含多个语言、多个系列型号或硬件变体，不能按 en-US 文件名推定全篇语言或参数适用范围。
本目录下的 verification.json 是采集时历史核验记录；layout-verification.json 是目录迁移后的路径、哈希与数据库一致性核验。

## 待人工处理

2 条 YouTube 官方视频要求登录/确认不是机器人；1 份 OPTEX 手册的 PDF 路径禁止机器人自动获取。本轮均未下载。
[人工操作清单](MANUAL_ACTIONS.md)。来源厂商版权保持原样，未公开发布原文件。

## 离线核验

在项目根目录执行：
```bash
uv run --group collection python -m pipelines.collection.organize_sample --run-id security_sample_20261027T070841Z
```
