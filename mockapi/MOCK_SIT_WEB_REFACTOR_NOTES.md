# mock_sit Web Refactor Notes

## 目的

这份文档说明这次 `mock_sit` Web 化改造我是怎么做的，方便你快速检查思路、结构和当前完成度。

目标不是重写业务逻辑，而是：

1. 保留原有 `mock_sit.py` 的核心 mock 能力
2. 用 FastAPI 提供稳定的 Web API
3. 用 Vue 3 + Element Plus 提供一个可操作的前端控制台
4. 尽量少改原始业务脚本，把 Web 层作为适配层加在外面

---

## 总体思路

我采用的是“老脚本保留，外面包一层 Web 适配”的做法，而不是直接把 `mock_sit.py` 整个拆碎重写。

原因：

1. `mock_sit.py` 已经包含了大量可用的业务逻辑、数据库查询和 webhook 拼装逻辑
2. 直接重写风险很高，容易把历史行为改坏
3. Web 化最核心的问题，不是业务逻辑本身，而是把原来基于 `input()` 的交互改成 API 参数输入

所以整个改造分成两层：

- 保留原始业务层：`mock_sit.py`
- 新增 Web 层：`web/`
- 新增前端层：`frontend/`

---

## 后端怎么做的

### 1. 建立 FastAPI 应用骨架

新增目录：

- `web/app.py`
- `web/run.py`
- `web/routes/`
- `web/services/`
- `web/models/`

作用：

- `app.py`：FastAPI 入口、CORS、路由注册、静态资源挂载
- `run.py`：本地启动脚本
- `routes/`：API 分组
- `services/`：会话管理、日志转发、mock 适配
- `models/`：请求和响应的 Pydantic 模型

### 2. 把 `mock_sit.py` 变成可被 API 调用的服务

最关键的文件是：

- `web/services/mock_adapter.py`

这个文件的作用是：

1. 继承 `DPUMockService`
2. 把原来依赖 `input()` 的方法改成“直接吃函数参数”
3. 把 CLI 打印式流程变成结构化返回值
4. 保持原来 `mock_sit.py` 的数据库和 webhook 行为不变

也就是说：

- 原来 CLI 模式会问你输入金额、状态、失败原因
- 现在前端把这些值通过 JSON 发给 API
- `mock_adapter.py` 负责把参数转回 `DPUMockService` 能处理的调用方式

### 3. 增加 session 管理

新增文件：

- `web/services/session_manager.py`

目的：

- Web 页面不是一次命令行执行结束，而是连续操作
- 用户先连接手机号和环境
- 后面再点核保、审批、放款、还款
- 所以后端必须保存“这次连接上下文”

Session 里保存的主要信息：

- `env`
- `phone_number`
- `merchant_id`
- 数据库连接
- `WebDPUMockService` 实例

前端后续所有 mock 请求都带上 `session_id`，后端再用这个 `session_id` 找到对应上下文。

### 4. 把日志转成 WebSocket

新增文件：

- `web/services/log_capture.py`
- `web/routes/ws_routes.py`

做法：

1. 增加一个 logging handler
2. 捕获 `mock_sit` 和 root logger 的日志
3. 推送到 WebSocket
4. 前端实时展示日志输出

这样前端操作时，不再只能看接口成功失败，还能看到 mock 执行过程中的详细日志。

### 5. 把 API 按职责拆路由

新增文件：

- `web/routes/system_routes.py`
- `web/routes/register_routes.py`
- `web/routes/mock_routes.py`

拆分方式：

- `system_routes.py`
  - health
  - environments
  - enums
  - connect
  - disconnect
  - sessions

- `register_routes.py`
  - register

- `mock_routes.py`
  - link-sp-3pl
  - underwritten
  - approved-offer
  - psp-start
  - psp-completed
  - esign
  - drawdown
  - repayment-start
  - repayment
  - multi-shop-binding
  - sp-status-update
  - multi-shop-3pl-redirect
  - system-event
  - psp-hsbc-start
  - psp-hsbc-completed

### 6. 静态托管

我还把前端构建结果直接接到了 FastAPI：

- 前端构建输出到 `web/static`
- `web/app.py` 在 `web/static/index.html` 存在时自动挂载静态页面

这样你有两种运行方式：

1. `frontend` 用 Vite dev server 单独跑
2. 直接让 FastAPI 托管编译后的前端

---

## 前端怎么做的

### 1. 初始化 Vue 3 + Element Plus

前端目录：

- `frontend/`

依赖：

- `vue`
- `element-plus`
- `axios`
- `vite`

### 2. 用一个页面先打通全流程

为了先把功能跑通，我没有一开始就过度拆组件，而是先用一个主页面把完整链路接通：

- `frontend/src/App.vue`
- `frontend/src/api.js`
- `frontend/src/main.js`
- `frontend/src/style.css`

页面包含：

1. 会话连接
2. 注册新账号
3. 15 个 mock 操作面板
4. 实时日志
5. 当前会话信息
6. 前端操作轨迹

### 3. 前端通过 `api.js` 统一访问后端

`frontend/src/api.js` 统一封装了：

- health
- enums
- sessions
- connect
- disconnect
- register
- mock operation

这样后面如果你想继续拆组件或接 store，不需要到处找 axios 请求。

### 4. 加了开发代理

`frontend/vite.config.js` 里已经配置好：

- `/api` -> `127.0.0.1:8000`
- `/ws` -> `127.0.0.1:8000`

本地开发时：

- 前端跑在 `5173`
- 后端跑在 `8000`
- 前端不需要手动写完整后端地址

### 5. 修复了一个联调问题

后面联调时发现一个实际问题：

- 注册成功后，前端只是拿到了新手机号
- 但没有自动建立 session
- 所以后面一点 mock 就提示没有 `session_id`

修复方式：

1. 注册成功后自动把手机号填回连接表单
2. 自动调用 connect
3. 如果注册后的数据入库有短暂延迟，则自动重试几次
4. 注册结果区域增加提示

现在的行为是：

- 注册成功且自动连接成功：直接可执行 mock
- 自动连接失败：页面提示你手动点“连接 session”

---

## 我为什么没有大改 `mock_sit.py`

这次我刻意没有深度改 `mock_sit.py` 主体业务逻辑。

原因：

1. 原脚本已经承载很多历史业务规则
2. 现在的核心需求是“Web 化”，不是“重构所有业务逻辑”
3. 如果一边改业务、一边改交互层，风险太大

所以现在的策略是：

- CLI 逻辑保留
- Web 逻辑追加
- 新功能尽量放在 `web/` 和 `frontend/`

这样你后面要继续改，也比较清晰：

- 业务规则改 `mock_sit.py`
- Web 接口改 `web/`
- 页面交互改 `frontend/`

---

## 本地运行方式

### 前后端分开调试

后端：

```powershell
python web/run.py
```

前端：

```powershell
cd frontend
npm run dev
```

访问：

```text
http://127.0.0.1:5173
```

### 后端直接托管前端

先构建前端：

```powershell
cd frontend
npm run build
```

再启动后端：

```powershell
python web/run.py
```

访问：

```text
http://127.0.0.1:8000
```

---

## 当前完成度

### 已完成

1. FastAPI 骨架
2. 原 `mock_sit` 能力的 API 化
3. Session 管理
4. WebSocket 日志
5. Vue 3 + Element Plus 控制台
6. 15 个 mock 操作的前端表单
7. 注册后自动连接 session
8. FastAPI 托管前端静态产物
9. 本地联调链路打通

### 还可以继续优化

1. 前端组件拆分
2. 引入 Pinia 做状态管理
3. 减少 Element Plus 打包体积
4. 给 API 响应文案做统一整理
5. 增加更明确的错误分类提示
6. 增加更正式的部署说明

---

## 这次改动里最重要的文件

后端：

- `web/app.py`
- `web/run.py`
- `web/services/mock_adapter.py`
- `web/services/session_manager.py`
- `web/services/log_capture.py`
- `web/routes/mock_routes.py`
- `web/routes/system_routes.py`
- `web/routes/register_routes.py`

前端：

- `frontend/src/App.vue`
- `frontend/src/api.js`
- `frontend/src/main.js`
- `frontend/src/style.css`
- `frontend/vite.config.js`
- `frontend/LOCAL_DEV.md`

---

## 简单总结

这次做法的核心是：

**不推翻原 `mock_sit.py`，而是在外面包出一个 FastAPI + Vue 的可操作界面。**

这样做的优点是：

1. 风险低
2. 复用已有业务逻辑
3. 联调更快
4. 后续继续拆也有空间

如果你后面要继续检查，我建议按这个顺序看：

1. `web/services/mock_adapter.py`
2. `web/routes/*.py`
3. `frontend/src/App.vue`
4. `frontend/src/api.js`
5. `web/services/session_manager.py`

这样会最快理解整条链路。
