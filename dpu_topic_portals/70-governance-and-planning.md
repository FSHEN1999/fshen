# 治理规划与需求源文档

聚焦短期计划、长期治理、AI 测试方案与需求设计源文件。

## 适合问这些问题
- 短期建设和长期治理文档各自负责什么
- 需求源文档里有哪些可供检索的设计信息

## 核心入口文件
- `DPU_2MONTH_TEST_PLAN.md`: # DPU 项目 2 个月自动化测试 / AI 测试短期方案 | ## 1. 目标 | ## 2. 对 DPU 项目的理解 | ### 2.1 状态模拟能力
- `DPU_2MONTH_TEST_PLAN_REPORT.md`: # DPU 项目自动化测试 / AI 测试两个月建设方案 | ## 一、项目背景 | ## 二、建设目标 | ## 三、本阶段覆盖范围
- `DPU_AUTOMATION_AI_TEST_PLAN.md`: # DPU 项目自动化测试 / AI 测试方案 | ## 1. 文档目的 | ## 2. 项目现状分析 | ### 2.1 现有资产
- `DPU_LONG_TERM_TEST_GOVERNANCE_REPORT.md`: # DPU 项目长期自动化测试 / AI 测试治理方案 | ## 一、方案定位 | ## 二、建设目标 | ### 1. 版本级自动回归
- `dpu模拟需求文档.docx`: task.md（dpu模型版本需求文档+设计文档） | 一、项目基本信息 | 1.项目名称：dpu模型版本 | 2.项目用途：为“提交信息即可完成贷款借款”的线上平台提供核心模型支撑，实现用户信息校验、借款资质评估、额度测算、风险防控等核心功能，保障平台借款流程高效、安全、合规，提升用户借款体验与平台风控能力。

## 快速检索命令
- `& '.\.venv\Scripts\python.exe' -m dpu_rag_mvp search "长期治理 版本回归 AI 报告"`
- `& '.\.venv\Scripts\python.exe' -m dpu_rag_mvp search "task requirement design document"`
- `& '.\.venv\Scripts\python.exe' -m dpu_rag_mvp search "两个月计划和长期治理的区别"`

## 推荐问法
- 长期治理 版本回归 AI 报告
- task requirement design document
- 两个月计划和长期治理的区别

## 关联主题
- `20-metersphere-mockapi`
- `30-migration-reg-prod`
