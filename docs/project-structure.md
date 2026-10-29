# 目录与文件管理约定

这是本项目的工程约定，不声称符合某项外部认证标准。

1. 前端代码、依赖及测试放 frontend/；当前已实现独立 React 应用。后端 /docs 是接口文档，不是独立前端。
2. 后端采用 backend/src/security_rag/ 的 src 包布局，独立 pyproject.toml。环境配置放 backend/.env，示例不含密钥。前端不得直接读 data/ 或连接数据库。
3. 离线采集、清洗、切分放 pipelines/；通过 Python 模块入口执行，不执行 logs/ 中的历史脚本快照。
4. SQL、数据库文件、备份分别归入 database/ 下的相应目录。数据库不放在源码或原始资料目录；当前未拆分 PostgreSQL 实例。
5. 清洗切分前的原始 PDF 唯一正式存放层为 data/raw/pdfs/<run_id>/<category>/<device_id>/。更新采用新版本，禁止原地清洗、删页、翻译或覆盖。
6. 视频归 raw/videos/，网页原始响应归 raw/webpages/，来源描述归 metadata/。预览和验证结果归 reports/；运行日志归 logs/。
7. 提取结果先进入 data/interim/extracted/，通过明确清洗步骤后才进入 processed/cleaned/；切分结果进入 processed/chunks/，记录输入哈希、配置与原文偏移。
8. 每次采集使用独立 run_id。当前清单 layout_version=2，path 和 extracted_path 一律相对项目根目录，不能相对清单所在目录解析。
9. 原始采集日志、历史命令、历史代码快照不改写。路径变化用 logs/migrations/ 的映射解释；迁移时保存原始清单、核验原件哈希并同步更新当前 manifest 和 SQLite metadata_json。
10. data/inbox/ 中的人工下载文件需先补来源、时间、哈希后再登记。失败或待人工文件不能标为 downloaded。
11. 根目录只放项目总览、依赖锁、忽略规则与工程约定。工具缓存不属于资料库，不提交 .venv、.cache、__pycache__ 和操作系统文件。

## 本轮迁移证据

98 个文件在移动前记录完整路径和 SHA-256，移动后逐一核对。记录位于 logs/migrations/20261027T071731Z/migration.json；原始清单与报告备份为该目录下的 original-* 文件。

9 份 PDF 原件逐字节一致。SQLite 保持 4 个设备目录、12 条资料状态及 145 页提取文本。当前清单和数据库路径已更新；历史日志保留当时路径，未伪造成新目录下执行。

## 当前清洗产物

全库清洗批次 cleaning_20261027T084605Z 已生成 1,888 页独立清洗文本与行级映射。输入、规则、哈希与发布记录位于 data/metadata/processing/；核验清单位于 reports/processing/；发布前备份位于 logs/processing/。上述迁移证据是历史时点，不代表当前提取覆盖率。
