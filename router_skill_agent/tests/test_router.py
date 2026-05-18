from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from router import choose_best, route  # noqa: E402
from skills.dpu_common import resolve_repo_python  # noqa: E402


class RouterTests(unittest.TestCase):
    def test_resolve_repo_python_returns_existing_interpreter(self) -> None:
        python_path = resolve_repo_python(Path("/Users/fshen/dpu"))
        self.assertTrue(python_path.exists())

    def test_routes_known_dpu_script_skill(self) -> None:
        routes = route("检查 mock_sit.py 语法", ["mock_sit.py"], execute=True)
        best, ambiguous = choose_best(routes)
        self.assertIsNotNone(best)
        assert best is not None
        self.assertEqual(best["name"], "dpu-script-check")
        self.assertTrue(best["executable"])
        self.assertFalse(ambiguous)

    def test_missing_required_input_blocks_execution(self) -> None:
        routes = route("检查 mock_sit.py 语法", [], execute=True)
        best, _ = choose_best(routes)
        self.assertIsNotNone(best)
        self.assertTrue(routes)
        script_check = next(item for item in routes if item["name"] == "dpu-script-check")
        self.assertTrue(script_check["missing_inputs"])
        self.assertFalse(script_check["executable"])
        assert best is not None
        self.assertEqual(best["name"], "dpu-mock-sit-health")

    def test_external_call_requires_explicit_risk(self) -> None:
        routes = route("我要调用后端接口做健康检查", ["http://127.0.0.1:8000/api/health"], execute=True)
        self.assertTrue(routes)
        api = next(item for item in routes if item["name"] == "api-health-check")
        self.assertFalse(api["executable"])
        self.assertIn("external_call", str(api["blocked_reason"]))

    def test_external_call_allowed_when_risk_is_set(self) -> None:
        routes = route(
            "我要调用后端接口做健康检查",
            ["http://127.0.0.1:8000/api/health"],
            allow_risk="external_call",
            execute=True,
        )
        api = next(item for item in routes if item["name"] == "api-health-check")
        self.assertTrue(api["executable"])


if __name__ == "__main__":
    unittest.main()
