# TestPilot AI Backend

FastAPI adapter for the TestPilot AI prototype.

## Run

```powershell
cd D:\data\project\dpu
.venv\Scripts\python.exe -m uvicorn ai-test-workbench.backend.app.main:app --reload --port 8010
```

If importing with the hyphenated folder name is inconvenient, run from inside the app folder:

```powershell
cd D:\data\project\dpu\ai-test-workbench
..\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8010
```

## Environment

Copy `.env.example` and set:

- `DIFY_API_KEY`
- `DIFY_DATASET_ID`
- `DIFY_GENERATE_WORKFLOW_KEY`
- `DIFY_REVIEW_WORKFLOW_KEY`

Without those values, the API returns stub responses so the frontend flow remains usable.
