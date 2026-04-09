# DPU RAG MVP

This repository now includes a local RAG MVP focused on DPU automation testing support.

## What It Does

- Builds a searchable local index over code, SOPs, runbooks, txt guides, and configs
- Surfaces automation-relevant files first
- Suggests likely scripts to run for a testing goal
- Exposes the same capabilities through an MCP server so Codex can use them directly
- Keeps MCP dependencies isolated in `.rag_mvp/venv` so the main project `.venv` stays stable

## Files

- `dpu_rag_mvp/cli.py`: CLI entrypoint
- `dpu_rag_mvp/core.py`: index build, search, automation suggestion logic
- `dpu_rag_mvp/mcp_server.py`: MCP server for Codex
- `scripts/install_dpu_rag_mvp.ps1`: reinstall dependencies and rebuild index
- `scripts/run_dpu_rag_mcp.ps1`: run the MCP server manually

## Commands

```powershell
& .\.venv\Scripts\python.exe -m dpu_rag_mvp build
& .\.venv\Scripts\python.exe -m dpu_rag_mvp status
& .\.venv\Scripts\python.exe -m dpu_rag_mvp search "hsbc psp completed"
& .\.venv\Scripts\python.exe -m dpu_rag_mvp suggest "帮我做 hsbc psp 自动化测试"
```

## Scope

Current MVP is lexical plus metadata-aware retrieval. It is intentionally lightweight:

- no remote vector database
- no external embedding dependency
- fast rebuild and low maintenance

It is designed to assist or replace manual script lookup during automation testing triage and execution planning.
