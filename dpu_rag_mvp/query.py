from __future__ import annotations

from dataclasses import dataclass


DPU_QUERY_ALIASES: dict[str, tuple[str, ...]] = {
    "reg": ("dpu-gateway-reg", "dpu_reg", "3307", "18.162.145.173"),
    "签约": ("esign", "esign.completed", "e_sign_status"),
    "电子签": ("esign", "esign.completed", "e_sign_status"),
    "esign": ("签约", "电子签", "esign.completed", "e_sign_status"),
    "审批": ("approved-offer", "approvedoffer.completed", "lenderApprovedOfferId"),
    "approved-offer": ("审批", "approvedoffer.completed", "lenderApprovedOfferId"),
    "核保": ("underwritten", "underwrittenLimit.completed", "underwrittenAmount"),
    "psp": ("psp-start", "psp-completed", "psp.verification.started", "psp.verification.completed"),
    "假成功": ("fake success", "top-level SUCCESS", "PENDING", "DB state", "report detail"),
    "米球": ("MeterSphere", "scenario", "report detail"),
    "metersphere": ("米球", "scenario", "report detail", "task-report"),
    "场景": ("scenario", "MeterSphere", ".ms"),
    "迁移": ("migration", "export_migration_json", "migration_data"),
    "多店铺": ("multi-shop", "3PL", "SP", "platform_seller_id"),
    "线下": ("offline", "selenium", "locators"),
    "线上": ("online", "offerId", "selenium", "locators"),
    "之前": ("history", "memory", "conversation"),
    "上次": ("history", "memory", "conversation"),
    "怎么定": ("decision", "memory", "conversation"),
}

MEMORY_INTENT_MARKERS = (
    "之前",
    "上次",
    "刚才",
    "历史",
    "记忆",
    "怎么定",
    "当时",
    "我们说",
    "我们做",
    "conversation",
    "memory",
    "decision",
)

PROJECT_INTENT_MARKERS = (
    ".py",
    ".ms",
    "脚本",
    "函数",
    "文件",
    "代码",
    "报错",
    "traceback",
    "stacktrace",
    "locator",
    "mock_sit",
    "mockapi",
    "migration",
)


@dataclass
class QueryRoute:
    route: str
    reasons: list[str]
    expanded_query: str


def expand_query(query: str) -> str:
    lowered = query.lower()
    expansions: list[str] = []
    for key, aliases in DPU_QUERY_ALIASES.items():
        if key.lower() in lowered:
            expansions.extend(alias for alias in aliases if alias.lower() not in lowered)
    if not expansions:
        return query
    return f"{query} {' '.join(dict.fromkeys(expansions))}"


def route_query(query: str) -> QueryRoute:
    lowered = query.lower()
    reasons: list[str] = []
    memory_score = 0
    project_score = 0

    for marker in MEMORY_INTENT_MARKERS:
        if marker.lower() in lowered:
            memory_score += 2
            reasons.append(f"memory:{marker}")
    for marker in PROJECT_INTENT_MARKERS:
        if marker.lower() in lowered:
            project_score += 2
            reasons.append(f"project:{marker}")

    if any(token in lowered for token in ("scenario_1", "metersphere", "reg", "mock_sit", "mockapi")):
        project_score += 1
        reasons.append("project:dpu-anchor")
    if any(token in lowered for token in ("之前", "上次", "历史")) and any(
        token in lowered for token in ("scenario", "reg", "mock", "metersphere", "rag")
    ):
        memory_score += 2
        project_score += 1
        reasons.append("hybrid:history-plus-project-anchor")

    if memory_score > project_score:
        route = "memory"
    elif project_score > memory_score:
        route = "project"
    else:
        route = "hybrid"
        reasons.append("hybrid:balanced-or-unclear")

    return QueryRoute(route=route, reasons=reasons[:8], expanded_query=expand_query(query))
