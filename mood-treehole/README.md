# 心情树洞 MVP

一个匿名优先、支持可选注册和管理员处置的心情树洞项目。

## 结构

- `backend/`：FastAPI + SQLite + Qwen 兼容接口
- `frontend/`：Vue + Vite 单页应用

## 启动后端

```powershell
cd mood-treehole\backend
copy .env.example .env
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

把你的千问参数写进 `backend/.env`：

```env
QWEN_BASE_URL=https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
QWEN_API_KEY=你的真实key
QWEN_MODEL=qwen3.6-plus
QWEN_TIMEOUT_SECONDS=90
```

管理员也在 `backend/.env` 里配置：

```env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=你自己的管理员密码
```

## 启动前端

```powershell
cd mood-treehole\frontend
copy .env.example .env
npm install
npm run dev
```

前端默认连 `http://127.0.0.1:8000`。

## 测试

```powershell
cd mood-treehole\backend
python -m pytest
```

## Docker + ngrok

```powershell
cd mood-treehole
docker compose up -d --build
ngrok http 8088
```

Docker 版会用 Nginx 托管前端，并把 `/api` 反向代理到后端 FastAPI。后端环境变量来自 `backend/.env`，本地访问地址是 `http://127.0.0.1:8088`。

## 说明

- 匿名用户会在浏览器里保存 `visitor_id`
- 普通用户可登录查看自己的历史
- 管理员可以查看、隐藏、删除和补充回复
- 如果 Qwen 不可用，后端会自动走本地兜底回复，不影响项目启动
