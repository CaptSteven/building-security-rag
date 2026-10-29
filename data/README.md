# 数据目录规范

- raw/pdfs/<run_id>/<category>/<device_id>/：清洗、切分前的 PDF 原件，独立目录，原件不覆盖。
- raw/videos/<run_id>/：下载成功的视频原件。目前为空，失败链接只在清单中记录。
- raw/webpages/<run_id>/：来源网页 HTML 与 robots.txt 原始响应；source_catalog 是采集发现阶段的入口快照。
- metadata/runs/<run_id>/：当前 manifest.json / manifest.csv；path 与 extracted_path 均相对项目根目录，禁止依赖当前终端工作目录解释路径。
- metadata/source_catalog/、metadata/source_snapshots/：来源描述元数据，和原始网页分开。
- interim/extracted/<run_id>/v1|v2/：未清洗的逐页提取文本；v2 只修复字体依赖，不代表完成清洗。
- processed/cleaned/<processing_run_id>/：逐页清洗文本 *.jsonl 和行级偏移 *.map.jsonl；不能存原始 PDF。
- processed/chunks/：切分产物，尚未生成；不能存未处理资料。
- inbox/<run_id>/：人工下载的待登记资料；先补来源及哈希，再进入原始资料层。

每轮使用独立 run_id。数据库文件存放在 database/，报告在 reports/，运行日志在 logs/。原件更新应创建新版本，不在原文件上清洗、删页或翻译。

metadata/processing/<processing_run_id>/ 保存输入快照、规则、处理清单与发布记录。原始提取层与清洗层以 PDF SHA-256、来源 run_id、asset_id、页码关联。当前清洗仅规范空白，不等于内容审核。
