---
name: dpu-rag-search
description: Search the DPU local RAG index to find relevant scripts, docs, MeterSphere context, mockapi flows, or prior project knowledge.
tags:
  - dpu
  - rag
  - search
  - metersphere
  - mockapi
  - context
  - 检索
  - 上下文
risk: read_only
inputs:
  - name: query
    type: text
    required: true
    description: Search query for the local DPU RAG index.
---

# DPU RAG Search

Use this skill when a DPU task needs project context before opening many files.

Inputs:

- search query

Output:

- local RAG status
- top search results
