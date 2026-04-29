# DPU RAG MVP

This repository now includes a local RAG MVP focused on DPU automation testing support.

## What It Does

- Builds a searchable local index over code, SOPs, runbooks, txt guides, and configs
- Exports local Codex session JSONL into `codex_sessions_rag/` so past conversations are searchable in the same RAG
- Reranks broad lexical hits so the top results are more likely to be directly useful
- Surfaces automation-relevant files first
- Suggests likely scripts to run for a testing goal
- Exposes the same capabilities through an MCP server so Codex can use them directly
- Keeps MCP dependencies isolated in `.rag_mvp/venv` so the main project `.venv` stays stable

## Files

- `dpu_rag_mvp/cli.py`: CLI entrypoint
- `dpu_rag_mvp/core.py`: index build, search, automation suggestion logic
- `dpu_rag_mvp/mcp_server.py`: MCP server for Codex
- `scripts/export_codex_sessions_to_rag.py`: exports `C:\Users\PC\.codex\sessions\**\*.jsonl` into Markdown chunks
- `scripts/sync_codex_sessions_to_rag.ps1`: exports sessions and rebuilds the RAG index
- `scripts/register_codex_session_rag_task.ps1`: registers a 15-minute Windows scheduled sync task
- `scripts/install_dpu_rag_mvp.ps1`: reinstall dependencies and rebuild index
- `scripts/run_dpu_rag_mcp.ps1`: run the MCP server manually

## Commands

```powershell
& .\.venv\Scripts\python.exe -m dpu_rag_mvp build
& .\.venv\Scripts\python.exe -m dpu_rag_mvp status
& .\.venv\Scripts\python.exe -m dpu_rag_mvp search "hsbc psp completed"
& .\.venv\Scripts\python.exe -m dpu_rag_mvp suggest "帮我做 hsbc psp 自动化测试"
```

## Search Rerank

`search` now uses a local usefulness reranker by default. It first collects a
broader lexical candidate set, then reorders candidates using exact query
matches, query-term coverage, path and tag matches, proximity inside the chunk,
conversation-memory intent, and noise penalties for tool-error fragments.

```powershell
& .\.venv\Scripts\python.exe -m dpu_rag_mvp search "Harness Engineering" --limit 5
& .\.venv\Scripts\python.exe -m dpu_rag_mvp search "scenario_1 scheduled task SUBMITTED" --candidate-limit 120
& .\.venv\Scripts\python.exe -m dpu_rag_mvp search "hsbc psp completed" --no-rerank
```

Each hit includes `rerank_score`, `matched_terms`, and `rerank_reasons` so you
can see why a result was promoted.

## Codex Conversation Sync

```powershell
& .\scripts\sync_codex_sessions_to_rag.ps1
& .\scripts\register_codex_session_rag_task.ps1
```

The sync exports useful `response_item` records from local Codex session JSONL files, writes generated Markdown under `codex_sessions_rag/`, and rebuilds the existing local RAG index. The generated directory is ignored by git because it is local machine memory, not source code.

## Scope

Current MVP is lexical plus metadata-aware retrieval. It is intentionally lightweight:

- no remote vector database
- no external embedding dependency
- fast rebuild and low maintenance

It is designed to assist or replace manual script lookup during automation testing triage and execution planning.
