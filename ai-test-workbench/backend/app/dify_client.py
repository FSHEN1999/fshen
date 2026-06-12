import os
from pathlib import Path
from typing import Any

import httpx


def load_local_env() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class DifyClient:
    def __init__(self) -> None:
        load_local_env()
        self.base_url = os.getenv("DIFY_BASE_URL", "https://api.dify.ai/v1").rstrip("/")
        self.api_key = os.getenv("DIFY_API_KEY", "")
        self.generate_key = os.getenv("DIFY_GENERATE_WORKFLOW_KEY", "")
        self.review_key = os.getenv("DIFY_REVIEW_WORKFLOW_KEY", "")
        self.dataset_id = os.getenv("DIFY_DATASET_ID", "")
        self.model_base_url = os.getenv("MODEL_BASE_URL", "").rstrip("/")
        self.model_api_key = os.getenv("MODEL_API_KEY", "")
        self.model_name = os.getenv("MODEL_NAME", "claude-sonnet-4-6")

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    @property
    def model_configured(self) -> bool:
        return bool(self.model_base_url and self.model_api_key and self.model_name)

    async def upload_document(self, filename: str, content: bytes, metadata: dict[str, Any]) -> dict[str, Any]:
        if not self.configured or not self.dataset_id:
            return {
                "provider": "stub",
                "document_id": f"stub-{filename}",
                "status": "queued",
                "message": "Dify dataset is not configured yet. Stored as a placeholder task.",
                "metadata": metadata,
            }

        url = f"{self.base_url}/datasets/{self.dataset_id}/document/create-by-file"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        data = {"data": '{"indexing_technique":"high_quality","process_rule":{"mode":"automatic"}}'}
        files = {"file": (filename, content)}

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, headers=headers, data=data, files=files)
            response.raise_for_status()
            return response.json()

    async def run_workflow(self, kind: str, inputs: dict[str, Any], user: str = "qa-user") -> dict[str, Any]:
        key = self.generate_key if kind == "generate" else self.review_key
        if not self.configured or not key:
            if self.model_configured:
                return await self._run_model(kind, inputs)
            return self._stub_workflow(kind, inputs)

        url = f"{self.base_url}/workflows/run"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        payload = {"inputs": inputs, "response_mode": "blocking", "user": user}

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    async def _run_model(self, kind: str, inputs: dict[str, Any]) -> dict[str, Any]:
        url = self._chat_completions_url()
        headers = {"Authorization": f"Bearer {self.model_api_key}", "Content-Type": "application/json"}
        system_prompt = self._system_prompt(kind)
        user_prompt = self._user_prompt(kind, inputs)
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.is_error:
                return {
                    "provider": "model",
                    "status": "failed",
                    "model": self.model_name,
                    "error": self._safe_error(response),
                    "inputs": inputs,
                }
            data = response.json()

        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return {
            "provider": "model",
            "status": "succeeded",
            "model": self.model_name,
            "output": {"content": content},
            "raw": data,
            "inputs": inputs,
        }

    def _safe_error(self, response: httpx.Response) -> dict[str, Any]:
        try:
            body = response.json()
        except ValueError:
            body = response.text[:500]
        return {
            "status_code": response.status_code,
            "body": body,
        }

    def _chat_completions_url(self) -> str:
        if self.model_base_url.endswith("/v1"):
            return f"{self.model_base_url}/chat/completions"
        return f"{self.model_base_url}/v1/chat/completions"

    def _system_prompt(self, kind: str) -> str:
        if kind == "generate":
            return (
                "You are a senior QA architect for the DPU financing platform. "
                "Generate concise, structured DPU test plans and test cases. "
                "Cover registration, SP authorization, PSP verification, E-sign, callbacks, negative paths, and observable assertions."
            )
        return (
            "You are a senior QA reviewer for the DPU financing platform. "
            "Review test cases for requirement coverage, negative paths, boundary values, executable steps, observable expected results, and missing assertions."
        )

    def _user_prompt(self, kind: str, inputs: dict[str, Any]) -> str:
        if kind == "generate":
            return (
                f"Project: {inputs.get('project')}\n"
                f"Release: {inputs.get('release')}\n"
                f"Suite: {inputs.get('suite')}\n"
                f"Output type: {inputs.get('output_type')}\n"
                f"Request: {inputs.get('prompt')}\n\n"
                "Return Markdown with sections: scope, risks, test cases table, and cited assumptions."
            )
        return (
            f"Project: {inputs.get('project')}\n"
            f"Release: {inputs.get('release')}\n"
            f"Suite: {inputs.get('suite')}\n"
            f"Criteria: {inputs.get('criteria')}\n"
            f"Cases:\n{inputs.get('content')}\n\n"
            "Return Markdown with score, high risk findings, per-case suggestions, and missing cases."
        )

    def _stub_workflow(self, kind: str, inputs: dict[str, Any]) -> dict[str, Any]:
        if kind == "generate":
            return {
                "provider": "stub",
                "status": "succeeded",
                "output": {
                    "summary": "Dify generate workflow is not configured yet. This is a backend placeholder response.",
                    "cases": [
                        {
                            "id": "TC-DPU-AI-001",
                            "title": "PSP timeout retry keeps financing workflow consistent",
                            "priority": "P0",
                            "source": "Stub workflow",
                        }
                    ],
                },
                "inputs": inputs,
            }
        return {
            "provider": "stub",
            "status": "succeeded",
            "output": {
                "score": 82,
                "findings": [
                    "Add webhook response assertions.",
                    "Add database status assertions for PSP timeout retry.",
                ],
            },
            "inputs": inputs,
        }
