# Frontend Local Dev

## Fastest way to try it

1. Start the backend from the repo root:

```powershell
python web/run.py
```

2. Start the frontend dev server in a new terminal:

```powershell
cd frontend
npm run dev
```

3. Open:

```text
http://127.0.0.1:5173
```

`vite.config.js` already proxies:

- `/api` -> `http://127.0.0.1:8000`
- `/ws` -> `ws://127.0.0.1:8000`

## Build and let FastAPI serve the frontend

From `frontend/`:

```powershell
npm run build
```

The build output goes to:

```text
../web/static
```

After that, with only the backend running, open:

```text
http://127.0.0.1:8000
```

## Notes

- Frontend dev mode is better for local debugging because you get HMR.
- Backend-only mode is useful when you want to verify the final packaged UI.
- WebSocket logs depend on connecting a valid session first.
