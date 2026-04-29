# 线下 UI 自动化

聚焦线下、DMF、手动输入版和暂停检查能力。

## 适合问这些问题
- 线下标准版、DMF 版、手动输入版分别适合什么场景
- 暂停检查能力在哪个模块里

## 核心入口文件
- `locators.py`: 页面元素定位器 - Page Object Model 组织，按页面分类管理元素定位 | symbols: RegistrationPage, PasswordSetupPage, CompanyInfoPage, DirectorInfoPage, BankAccountPage, ContactInfoPage
- `pause_manager.py`: 暂停管理器 - 支持通过空格键暂停/继续自动化脚本 | symbols: StopScriptException, PauseManager, get_pause_manager, check_pause
- `ui_helpers.py`: UI助手模块 - 统一管理UI操作，优化等待逻辑，避免重复的waitUntil调用 | symbols: SmartWait, UIOperations
- `线下自动化.py`: HSBC 线下自动化注册工具 | symbols: Config, setup_logging, generate_uuid, get_utc_time, get_local_time_str, get_user_choice
- `线下自动化hsbc.py`: HSBC 线下自动化注册工具 (DMF版本) | symbols: Config, setup_logging, generate_uuid, get_utc_time, get_local_time_str, generate_mock_id_number

## 快速检索命令
- `& '.\.venv\Scripts\python.exe' -m dpu_rag_mvp search "线下自动化 dmf 手动输入版 差异"`
- `& '.\.venv\Scripts\python.exe' -m dpu_rag_mvp search "offline hsbc automation pause_manager"`
- `& '.\.venv\Scripts\python.exe' -m dpu_rag_mvp search "线下脚本走哪些页面元素定位器"`

## 推荐问法
- 线下自动化 dmf 手动输入版 差异
- offline hsbc automation pause_manager
- 线下脚本走哪些页面元素定位器

## 关联主题
- `50-online-ui-automation`
- `10-mock-core-flow`
