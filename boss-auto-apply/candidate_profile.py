"""Candidate profile helpers.

Keep personal resume data configurable instead of hardcoding it in automation
code. Values here are safe placeholders until .env.local.ps1 is filled.
"""
from __future__ import annotations

import os
import re
from pathlib import Path


def _load_local_ps_env() -> None:
    env_path = Path(__file__).parent / ".env.local.ps1"
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text(encoding="utf-8-sig").splitlines():
            match = re.match(r'^\s*\$env:([A-Za-z_][A-Za-z0-9_]*)\s*=\s*["\'](.*)["\']\s*$', line)
            if match and not os.environ.get(match.group(1)):
                os.environ[match.group(1)] = match.group(2)
    except Exception:
        return


_load_local_ps_env()


def _env(name: str, default: str = "") -> str:
    value = os.environ.get(name, "").strip()
    return value or default


def _env_list(name: str, default: list[str]) -> list[str]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


def load_resume() -> dict:
    _load_local_ps_env()
    return {
        "name": _env("BOSS_CANDIDATE_NAME", "候选人"),
        "phone": _env("BOSS_CANDIDATE_PHONE", "待填写"),
        "email": _env("BOSS_CANDIDATE_EMAIL", "待填写"),
        "city": _env("BOSS_CANDIDATE_CITY", "深圳"),
        "experience": _env("BOSS_CANDIDATE_EXPERIENCE", "待填写"),
        "education": _env("BOSS_CANDIDATE_EDUCATION", "待填写"),
        "school": _env("BOSS_CANDIDATE_SCHOOL", "待填写"),
        "major": _env("BOSS_CANDIDATE_MAJOR", "待填写"),
        "grad_year": _env("BOSS_CANDIDATE_GRAD_YEAR", "待填写"),
        "current_company": _env("BOSS_CANDIDATE_CURRENT_COMPANY", "待填写"),
        "current_title": _env("BOSS_CANDIDATE_CURRENT_TITLE", "待填写"),
        "skills": _env_list(
            "BOSS_CANDIDATE_SKILLS",
            ["测试管理", "接口测试", "自动化测试", "Python", "Selenium", "Requests", "MySQL"],
        ),
        "highlights": _env_list(
            "BOSS_CANDIDATE_HIGHLIGHTS",
            ["项目经历待根据简历补充"],
        ),
        "salary_expect": _env("BOSS_CANDIDATE_SALARY_EXPECT", "面议"),
        "available": _env("BOSS_CANDIDATE_AVAILABLE", "可沟通"),
        "target_direction": _env("BOSS_CANDIDATE_TARGET_DIRECTION", "测试开发 / 测试负责人"),
    }


def resume_brief() -> str:
    _load_local_ps_env()
    resume = load_resume()
    skills = "、".join(resume["skills"][:8]) or "待填写"
    highlights = "；".join(resume["highlights"][:4]) or "待填写"
    return (
        f"{resume['name']} {resume['experience']} {resume['target_direction']} "
        f"{resume['city']} {resume['available']}\n"
        f"- 当前/最近：{resume['current_company']} / {resume['current_title']}\n"
        f"- 技术栈：{skills}\n"
        f"- 项目亮点：{highlights}\n"
        f"- 期望：{resume['salary_expect']} / {resume['city']}"
    )


def missing_required_fields() -> list[str]:
    resume = load_resume()
    required = {
        "BOSS_CANDIDATE_NAME": resume["name"],
        "BOSS_CANDIDATE_PHONE": resume["phone"],
        "BOSS_CANDIDATE_EXPERIENCE": resume["experience"],
        "BOSS_CANDIDATE_CURRENT_TITLE": resume["current_title"],
    }
    missing = []
    for key, value in required.items():
        if not value or value.startswith("待填写") or value.startswith("replace-with") or value == "候选人":
            missing.append(key)
    return missing
