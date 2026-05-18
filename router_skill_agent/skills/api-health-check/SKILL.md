---
name: api-health-check
description: Check an HTTP API health endpoint and return status code plus response body.
tags:
  - api
  - backend
  - health
  - http
  - 接口
  - 后端
risk: external_call
inputs:
  - name: url
    type: url
    required: true
    description: HTTP health endpoint to request.
---

# API Health Check

Use this skill when the user wants to verify that a backend service is up.

Input:

- health URL

Output:

- HTTP status
- response body
