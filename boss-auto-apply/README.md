# boss-auto-apply

BOSS 直聘本地自动求职助手。当前主线是测试开发 / 测试负责人 / Agent 测试方向：自动筛选岗位、发送招呼语、监听 HR 未读消息、用 AI 生成回复、按策略发送在线简历，并记录状态和日志。

## 日常入口

```bat
start.bat                    :: 唯一日常入口：先效率投递，再慢速 AI 回复 HR
run_dashboard.bat            :: 打开本地只读看板 http://127.0.0.1:8765
run_monitor_gui.bat          :: 打开桌面可视化监视窗口
sync_storage.bat             :: 把现有 CSV/JSON 运行数据同步到 SQLite
status.bat                   :: 查看当前阶段、岗位、进度
watch_apply_log.bat          :: 实时查看 data/run.log
stop_apply.bat               :: 停止运行中的 Python 自动化进程
```

`start.bat` 默认投 5 个岗位，然后每 180 秒轮询一次未读 HR 消息并自动回复。可传参数：

```bat
start.bat             :: 投 5 个，180 秒慢轮询，永久运行
start.bat 10 300 0    :: 投 10 个，300 秒慢轮询，永久运行
start.bat --check     :: 只做语法检查和 doctor，不启动投递
```

旧启动脚本已删除，避免误点。需要运行就用 `start.bat`，需要看状态就用 `status.bat` / `watch_apply_log.bat`。

## AI 聊天

默认入口会启用：

```bat
BOSS_AI_REPLY=1
BOSS_AI_PROVIDER=qwen
BOSS_QWEN_MODEL=qwen3.6-plus
BOSS_RAG_ENABLE=1
```

真实 key 放在被 git 忽略的 `.env.local.ps1`：

```powershell
$env:BOSS_AI_PROVIDER = "qwen"
$env:BOSS_QWEN_BASE_URL = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
$env:BOSS_QWEN_MODEL = "qwen3.6-plus"
$env:BOSS_QWEN_API_KEY = "你的key"
```

AI 调用日志写入 `data/ai_calls.jsonl`，包含 provider、model、purpose、耗时和回复文本，不记录 API key。

AI 回复发送前会经过本地校验：

- 过长回复会截断到适合 BOSS 聊天的长度。
- 禁止出现“我是AI/作为AI”等暴露自动化的文本。
- 薪资、到岗、联系方式、简历类回复会去掉无意义反问。
- 命中风险文本时会使用本地兜底话术。

## 简历策略

- 默认只发送 BOSS 在线简历。
- 附件 PDF 上传默认关闭，只有显式设置 `BOSS_ALLOW_UPLOAD_RESUME=1` 才允许。
- HR 有新消息时，聊天监听会自动回复；如果该会话还没有记录简历已发送，会追加在线简历动作。
- 已记录 `confirmed_in_chat`、`sent_by_sweep`、`sent_by_chat_action` 的会话不会重复发简历。

## 自检

```bat
python main.py --doctor
python doctor.py --json
```

自检会检查 Python、DrissionPage、`config.yaml`、Chrome profile、debug port、AI provider 配置、关键状态文件。

## 看板

```bat
run_dashboard.bat
```

浏览器打开 `http://127.0.0.1:8765`，可以看当前状态、今日投递、HR 待办、最近 AI 调用和面试记录。看板也提供本地操作按钮：

```text
开始 start.bat
停止 stop_apply.bat
```

为了避免误启动多个自动化进程，`start.bat` 会创建 `data/run.lock`。如果已有任务在跑，会直接拒绝重复启动。`stop_apply.bat` 会停止进程并释放锁。

## SQLite 数据层

当前不替换运行中的 JSON/CSV，只提供增量同步层：

```bat
sync_storage.bat
```

输出数据库在 `data/boss_data.db`，已加入 `.gitignore`。后续可以基于它做更完整的统计、筛选、复盘和追踪。

## 常用命令

```bat
python main.py --login
python main.py --run --limit 5
python main.py --chat-watch --interval 180 --rounds 0
python main.py --resume-sweep-dry --limit 50
python main.py --report
```

## 安全边界

不要提交以下内容：

- `.env.local.ps1`
- `config.yaml`
- `data/chrome_profile*`
- `data/cookies*.json`
- `data/dom_dumps/`
- `data/*.log`
- `data/ai_calls.jsonl`
- `data/boss_data.db*`
- `logs/`

提交前先看：

```bat
git status --short
git diff --stat
```
