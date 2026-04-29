# 线上 UI 自动化

聚焦 offerId 生成、线上注册、TIER 流程和浏览器自动化脚本。

## 适合问这些问题
- 线上流程的脚本入口和 TIER 差异在哪里
- offerId 生成脚本和完整自动化脚本怎么配合

## 核心入口文件
- `locators.py`: 页面元素定位器 - Page Object Model 组织，按页面分类管理元素定位 | symbols: RegistrationPage, PasswordSetupPage, CompanyInfoPage, DirectorInfoPage, BankAccountPage, ContactInfoPage
- `pause_manager.py`: 暂停管理器 - 支持通过空格键暂停/继续自动化脚本 | symbols: StopScriptException, PauseManager, get_pause_manager, check_pause
- `sit 批量生成offerid.py`: 发送POST请求并返回提取到的amazon3plOfferId | symbols: send_request, get_user_choice, main
- `uat 批量生成offerid.py`: 发送POST请求并返回提取到的amazon3plOfferId | symbols: send_request, get_user_choice, main
- `ui_helpers.py`: UI助手模块 - 统一管理UI操作，优化等待逻辑，避免重复的waitUntil调用 | symbols: SmartWait, UIOperations
- `线上自动化.py`: HSBC API 数据生成与自动注册工具 | symbols: AppConfig, setup_logging, send_post_request, poll_credit_offer_status, poll_drawdown_status, get_local_physical_ip
- `线上自动化tier3.py`: HSBC API 数据生成与自动注册工具 - TIER3固定版本 | symbols: AppConfig, setup_logging, send_post_request, poll_credit_offer_status, poll_drawdown_status, get_local_physical_ip

## 快速检索命令
- `& '.\.venv\Scripts\python.exe' -m dpu_rag_mvp search "线上自动化 tier2 tier3 offerid"`
- `& '.\.venv\Scripts\python.exe' -m dpu_rag_mvp search "线上注册脚本和 locators 对应关系"`
- `& '.\.venv\Scripts\python.exe' -m dpu_rag_mvp search "哪个脚本会在 SP 完成后停住"`

## 推荐问法
- 线上自动化 tier2 tier3 offerid
- 线上注册脚本和 locators 对应关系
- 哪个脚本会在 SP 完成后停住

## 关联主题
- `60-offline-ui-automation`
- `10-mock-core-flow`
