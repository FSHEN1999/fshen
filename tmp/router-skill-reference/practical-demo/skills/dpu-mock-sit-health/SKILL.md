---
name: dpu-mock-sit-health
description: Inspect mock_sit.py safely by compile-checking it and extracting important DPU mock operation names.
tags:
  - dpu
  - mock_sit
  - mock
  - health
  - status
  - webhook
  - 体检
  - 模拟
---

# DPU mock_sit Health

Use this skill before changing or running `mock_sit.py`.

It does not trigger real workflow callbacks. It only:

- compile-checks `mock_sit.py`
- extracts operation/function names
- reports whether important flow keywords are present

