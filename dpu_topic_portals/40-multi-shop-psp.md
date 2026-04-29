# 多店铺与 PSP 专题

聚焦多店铺绑定、3PL 跳转、PSP 记录插入与额度拆分。

## 适合问这些问题
- 多店铺场景里先绑 SP 还是先绑 PSP
- 额度拆分和 psp_status 更新在哪个脚本里

## 核心入口文件
- `SOP_多店铺PSP绑定脚本.md`: # 多店铺PSP绑定脚本 SOP | ## 一、脚本概述 | ## 二、执行前准备 | ### 2.1 环境配置
- `migration_test_FP_json 多店铺绑定psp.py`: 多店铺PSP绑定脚本 | symbols: ExecuteSql, __init__, __enter__, __exit__, execute_sql, generate_random_str
- `mock_sit.py`: DPU状态模拟工具 | symbols: ColorFormatter, generate_uuid37, validate_phone_number, get_current_time, get_utc_time, validate_numeric_input
- `mock_uat.py`: DPU状态模拟工具 | symbols: ColorFormatter, generate_uuid37, validate_phone_number, get_current_time, get_utc_time, validate_numeric_input
- `mockapi/METERSPHERE_INTEGRATION_DESIGN.md`: # MeterSphere 接入设计文档 | ## 1. 一句话结论 | ## 2. 背景与目标 | ## 3. 为什么选 `mockapi/web/app.py`

## 快速检索命令
- `& '.\.venv\Scripts\python.exe' -m dpu_rag_mvp search "multi shop psp binding 3pl redirect"`
- `& '.\.venv\Scripts\python.exe' -m dpu_rag_mvp search "多店铺 PSP 绑定脚本 SOP"`
- `& '.\.venv\Scripts\python.exe' -m dpu_rag_mvp search "mock_multi_shop_binding mock_multi_shop_3pl_redirect"`

## 推荐问法
- multi shop psp binding 3pl redirect
- 多店铺 PSP 绑定脚本 SOP
- mock_multi_shop_binding mock_multi_shop_3pl_redirect

## 关联主题
- `10-mock-core-flow`
- `30-migration-reg-prod`
