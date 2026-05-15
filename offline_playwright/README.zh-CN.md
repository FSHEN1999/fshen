# DPU 线下自动化 Playwright 版

这个目录是 REG 普通线下流程的 Playwright clean runner。它和旧 Selenium 脚本并行存在，不会 import 或修改 `线下自动化.py`、`线下自动化hsbc.py`、`locators.py`。

## 适用范围

- 首版只覆盖 REG 普通线下主链路。
- 不覆盖 HSBC DMF。
- 不兼容 QQ / 360 浏览器矩阵；Playwright 版优先使用 Chromium。
- 成功标准不是“日志显示点击成功”，而是 UI 关键步骤完成后，数据库能查到对应业务状态。

## 安装依赖

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-playwright.txt
.\.venv\Scripts\python.exe -m playwright install chromium
```

浏览器缓存会放到项目目录下的 `.playwright-browsers/`，避免落到 `C:\Windows\System32` 等无权限目录。

## 运行命令

完整运行 REG 普通线下主链：

```powershell
.\.venv\Scripts\python.exe -m offline_playwright.runner --env reg --headed
```

指定手机号：

```powershell
.\.venv\Scripts\python.exe -m offline_playwright.runner --env reg --headed --phone 18212345678
```

调试时停在 final apply 后：

```powershell
.\.venv\Scripts\python.exe -m offline_playwright.runner --env reg --headed --stop-after final_apply
```

调试时停在融资方案选择后：

```powershell
.\.venv\Scripts\python.exe -m offline_playwright.runner --env reg --headed --stop-after financing
```

降低执行速度，方便观察页面：

```powershell
.\.venv\Scripts\python.exe -m offline_playwright.runner --env reg --headed --slow-mo 300
```

## 输出文件

每次运行都会生成独立目录：

```text
output/playwright/offline/<timestamp>/
```

里面包含：

- `run.log`：运行日志
- `trace.zip`：Playwright trace，可用于回放每一步操作
- `failure.png`：失败时的整页截图
- `videos/`：浏览器录屏

## 当前流程

首版 runner 的主流程：

1. 打开 REG 线下注册页。
2. 自动生成或使用指定手机号。
3. 填写手机号和短信验证码。
4. 设置密码、安全问题、邮箱并注册。
5. 点击 final apply。
6. 轮询数据库，确认 SP 授权 `state` 已入库。
7. 打开 SP 授权 URL。
8. 查询 `idempotency_key` 和 `platform_offer_id`。
9. 调用 `/dpu-auth/amazon-sp/updateOffer`。
10. 如 `send_status=SUCCESS`，打开 3PL redirect URL。
11. 填写公司信息。
12. 填写董事信息。
13. 选择融资方案。
14. 调用 `link-sp-3pl-shops`。

## Selenium 和 Playwright 的区别

Selenium 更像是通过 WebDriver 远程控制浏览器。很多事情需要脚本自己处理，比如等待元素可点击、页面是否加载完成、按钮是否真的触发后续状态。因此旧脚本里会有很多 `WebDriverWait`、备用 XPath、JS 点击、手写重试。

Playwright 更像是为现代 Web 应用设计的自动化运行时。它会在点击、输入前自动判断元素是否可见、稳定、可操作，也能直接生成 trace、截图和视频。对 DPU 这种 Vue / Element UI 动态表单来说，失败后更容易判断是没找到元素、没点到、页面没跳、接口没返回，还是数据库状态没变化。

这次重构不是把 Selenium 代码逐行翻译成 Playwright，而是把线下自动化拆成更清楚的结构：

- `settings.py`：环境、URL、数据库、artifact 配置
- `db.py`：数据库查询和最终状态校验
- `pages.py`：Playwright 页面动作
- `runner.py`：流程编排和命令行入口

后续如果扩展 HSBC 或更多分支，优先新增页面对象和 runner 参数，不建议把逻辑重新堆回一个大脚本。

## 验证命令

```powershell
.\.venv\Scripts\python.exe -m py_compile .\offline_playwright\__init__.py .\offline_playwright\settings.py .\offline_playwright\db.py .\offline_playwright\pages.py .\offline_playwright\runner.py
.\.venv\Scripts\python.exe -m offline_playwright.runner --help
```
