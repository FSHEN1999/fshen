# 迁移脚本与 reg 生产回传

聚焦 batch1、batch3、多店铺 PSP 绑定、数据导出、回滚与 reg 环境。

## 适合问这些问题
- batch1、batch3 和多店铺 PSP 绑定脚本的职责怎么分
- 回滚和导出 JSON 的入口在哪里

## 核心入口文件
- `dpu模拟需求文档.docx`: task.md（dpu模型版本需求文档+设计文档） | 一、项目基本信息 | 1.项目名称：dpu模型版本 | 2.项目用途：为“提交信息即可完成贷款借款”的线上平台提供核心模型支撑，实现用户信息校验、借款资质评估、额度测算、风险防控等核心功能，保障平台借款流程高效、安全、合规，提升用户借款体验与平台风控能力。
- `export_migration_json.py`: 数据抽取脚本 - 从数据库抽取迁移数据并生成JSON格式 | symbols: DatabaseExecutor, MigrationDataExporter, print_split_jsons, main
- `migration_data.json`: { | "brn": "76380727", | "lender_approved_offer_id": "app-MIGRATION-76380727", | "lender_credit_id": "cred-MIGRATION-76380727",
- `migration_test_FP.py`: 生成随机字符串 | symbols: ExecuteSql, generate_random_str, generate_random_hex, check_and_execute, run_application
- `migration_test_FP_json batch1.py`: 迁移测试脚本 - 支持 JSON 格式导入 | symbols: ExecuteSql, __init__, __enter__, __exit__, execute_sql, generate_random_str
- `migration_test_FP_json batch3.py`: 迁移测试脚本 - 支持 JSON 格式导入 | symbols: ExecuteSql, __init__, __enter__, __exit__, execute_sql, generate_random_str
- `migration_test_FP_json 多店铺绑定psp.py`: 多店铺PSP绑定脚本 | symbols: ExecuteSql, __init__, __enter__, __exit__, execute_sql, generate_random_str
- `rollback_migration.py`: 回滚脚本 - 删除迁移数据（匹配 migration_test_FP_json用户1-无法支持多店铺.py） | symbols: ExecuteSql, check_and_execute, rollback
- `update_currency.py`: Python module

## 快速检索命令
- `& '.\.venv\Scripts\python.exe' -m dpu_rag_mvp search "migration batch1 batch3 export rollback reg"`
- `& '.\.venv\Scripts\python.exe' -m dpu_rag_mvp search "生产迁移回传 FP json 怎么导出"`
- `& '.\.venv\Scripts\python.exe' -m dpu_rag_mvp search "task.md 里和 migration 相关的要求是什么"`

## 推荐问法
- migration batch1 batch3 export rollback reg
- 生产迁移回传 FP json 怎么导出
- task.md 里和 migration 相关的要求是什么

## 关联主题
- `40-multi-shop-psp`
- `70-governance-and-planning`
