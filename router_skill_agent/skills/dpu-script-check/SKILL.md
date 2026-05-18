---
name: dpu-script-check
description: Compile-check a DPU Python script without running its business workflow.
tags:
  - dpu
  - python
  - py_compile
  - syntax
  - script
  - mock_sit
  - 脚本
  - 语法
risk: read_only
inputs:
  - name: script_path
    type: file
    required: true
    description: Python script path relative to the DPU repository root.
---

# DPU Script Check

Use this skill before running or editing a DPU Python script.

Inputs:

- path relative to `D:\data\project\dpu`, such as `mock_sit.py`

Output:

- compile result
- stderr if syntax/import path issues are found
