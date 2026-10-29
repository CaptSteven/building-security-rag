# 文本提取与保守清洗报告

处理批次：`cleaning_20261027T084605Z`。规则：`conservative-whitespace-v1`。

处理 110/110 份 PDF，共 1888 页；66 份资料的 550 页出现自动核验标记。

原始 PDF 保持不变；提取文本、清洗文本、逐行区间映射分别保存。未删除页面，不补写产品参数，不自动拼词、合并连字符或重排表格。重复页眉页脚仅列为候选，不自动删除。

规范化前 2,599,649 字符，之后 2,595,728 字符，186 页有格式变化。减少的字符不等于去掉了无用知识，完整变更可由映射复核。

## 质量标记

| 标记 | 页数 |
|---|---:|
| empty_or_image_page | 33 |
| numeric_layout_review | 33 |
| possible_fused_words | 53 |
| sparse_text_page | 293 |
| fragmented_short_lines | 145 |

[待核验页 CSV](quality.csv) · [机器可读统计](summary.json)

逐页标记和重复边缘行候选在 data/metadata/processing/<本批次>/manifest.json；逐行映射在 data/processed/cleaned/<本批次>/*.map.jsonl。offset 为 Unicode 字符下标，右端不含。它是行级区间映射，不声称逐字符一一对应。

## 当前边界

自动格式清洗不等于人工事实审核。扫描件/空页、疑似单词黏连、碎行、乱码和密集数字布局需要核对 PDF 原件。没有进行 OCR，也没有做文档切分或向量化。

[五类标记定向抽查记录](inspection/observations.md) · [原件预览拼图](inspection/contact-sheet.jpg)。正式人工核验尚未完成。
