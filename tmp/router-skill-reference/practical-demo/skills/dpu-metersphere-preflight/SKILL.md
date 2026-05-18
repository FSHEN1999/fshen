---
name: dpu-metersphere-preflight
description: Prepare for a DPU MeterSphere run by locating known run harnesses and reporting required environment variables without executing a live scenario.
tags:
  - dpu
  - metersphere
  - scenario
  - preflight
  - report
  - REG
  - 场景
  - 实跑
---

# DPU MeterSphere Preflight

Use this skill before a live MeterSphere run.

This skill is intentionally safe by default. It does not import or execute a MeterSphere scene.

It reports:

- known local MeterSphere harness scripts
- whether likely token/session environment variables are set
- recommended next command shape

