from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile, is_zipfile


TEXT_ENCODINGS = ("utf-8", "utf-8-sig", "gb18030", "gbk", "utf-16")
WORDPROCESSINGML_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


@dataclass(frozen=True)
class TopicDefinition:
    slug: str
    title: str
    summary: str
    patterns: tuple[str, ...]
    starter_queries: tuple[str, ...]
    questions: tuple[str, ...]
    related_topics: tuple[str, ...] = ()


@dataclass
class TopicPortalInfo:
    slug: str
    title: str
    summary: str
    rel_path: str
    file_count: int
    top_files: list[str]
    starter_queries: list[str]


TOPIC_DEFINITIONS = (
    TopicDefinition(
        slug="00-project-map",
        title="项目总览与主入口",
        summary="先定位核心脚本族、Web 接入层、数据库辅助层和长文档来源。",
        patterns=(
            "AGENTS.md",
            "mock_uat.py",
            "mock_sit.py",
            "db_helper.py",
            "config.py",
            "webhook_service.py",
            "locators.py",
            "dpu_rag_mvp/*.py",
            "mockapi/AGENTS.md",
            "mockapi/web/app.py",
        ),
        starter_queries=(
            "项目主入口是什么",
            "mock_uat mockapi db_helper 关系",
            "先看哪些文件能快速理解 DPU 项目",
        ),
        questions=(
            "这个仓库的主入口和辅助层分别是什么",
            "CLI、Web、数据库、UI 自动化分别落在哪些文件",
        ),
        related_topics=("10-mock-core-flow", "20-metersphere-mockapi"),
    ),
    TopicDefinition(
        slug="10-mock-core-flow",
        title="核心 Mock 状态流",
        summary="聚焦注册、核保、审批、PSP、电子签、放款、还款等主流程。",
        patterns=(
            "mock_uat.py",
            "mock_sit.py",
            "db_helper.py",
            "webhook_service.py",
            "config.py",
            "mockapi/web/services/mock_adapter.py",
        ),
        starter_queries=(
            "underwritten approved psp esign drawdown repayment 流程",
            "merchant_id application_unique_id 是怎么串起来的",
            "mock_uat 里主流程方法有哪些",
        ),
        questions=(
            "主流程里关键 ID 是怎么从数据库取出来的",
            "核保到放款之间的状态更新入口在哪里",
        ),
        related_topics=("20-metersphere-mockapi", "40-multi-shop-psp"),
    ),
    TopicDefinition(
        slug="20-metersphere-mockapi",
        title="MeterSphere 与 mockapi 接入",
        summary="聚焦 FastAPI 接入层、会话模型、接口清单与 MeterSphere 变量设计。",
        patterns=(
            "mockapi/METERSPHERE_INTEGRATION_DESIGN.md",
            "mockapi/INTEGRATION_GUIDE.md",
            "mockapi/web/app.py",
            "mockapi/web/routes/*.py",
            "mockapi/web/models/*.py",
            "mockapi/web/services/*.py",
        ),
        starter_queries=(
            "metersphere session_id scene variable",
            "mockapi web app 路由和服务层怎么分",
            "MeterSphere 应该怎么接 mockapi",
        ),
        questions=(
            "MeterSphere 最佳主入口为什么是 mockapi/web/app.py",
            "session_id、phone_number 这些变量应该怎样传递",
        ),
        related_topics=("10-mock-core-flow", "70-governance-and-planning"),
    ),
    TopicDefinition(
        slug="30-migration-reg-prod",
        title="迁移脚本与 reg 生产回传",
        summary="聚焦 batch1、batch3、多店铺 PSP 绑定、数据导出、回滚与 reg 环境。",
        patterns=(
            "migration_test_FP.py",
            "migration_test_FP_json batch1.py",
            "migration_test_FP_json batch3.py",
            "migration_test_FP_json 多店铺绑定psp.py",
            "migration_data.json",
            "export_migration_json.py",
            "rollback_migration.py",
            "update_currency.py",
            "dpu模拟需求文档.docx",
            "*需求文档*.pdf",
        ),
        starter_queries=(
            "migration batch1 batch3 export rollback reg",
            "生产迁移回传 FP json 怎么导出",
            "task.md 里和 migration 相关的要求是什么",
        ),
        questions=(
            "batch1、batch3 和多店铺 PSP 绑定脚本的职责怎么分",
            "回滚和导出 JSON 的入口在哪里",
        ),
        related_topics=("40-multi-shop-psp", "70-governance-and-planning"),
    ),
    TopicDefinition(
        slug="40-multi-shop-psp",
        title="多店铺与 PSP 专题",
        summary="聚焦多店铺绑定、3PL 跳转、PSP 记录插入与额度拆分。",
        patterns=(
            "SOP*.md",
            "migration_test_FP_json 多店铺绑定psp.py",
            "mock_uat.py",
            "mock_sit.py",
            "mockapi/METERSPHERE_INTEGRATION_DESIGN.md",
        ),
        starter_queries=(
            "multi shop psp binding 3pl redirect",
            "多店铺 PSP 绑定脚本 SOP",
            "mock_multi_shop_binding mock_multi_shop_3pl_redirect",
        ),
        questions=(
            "多店铺场景里先绑 SP 还是先绑 PSP",
            "额度拆分和 psp_status 更新在哪个脚本里",
        ),
        related_topics=("10-mock-core-flow", "30-migration-reg-prod"),
    ),
    TopicDefinition(
        slug="50-online-ui-automation",
        title="线上 UI 自动化",
        summary="聚焦 offerId 生成、线上注册、TIER 流程和浏览器自动化脚本。",
        patterns=(
            "*线上*.py",
            "*批量生成offerid.py",
            "locators.py",
            "ui_helpers.py",
            "pause_manager.py",
        ),
        starter_queries=(
            "线上自动化 tier2 tier3 offerid",
            "线上注册脚本和 locators 对应关系",
            "哪个脚本会在 SP 完成后停住",
        ),
        questions=(
            "线上流程的脚本入口和 TIER 差异在哪里",
            "offerId 生成脚本和完整自动化脚本怎么配合",
        ),
        related_topics=("60-offline-ui-automation", "10-mock-core-flow"),
    ),
    TopicDefinition(
        slug="60-offline-ui-automation",
        title="线下 UI 自动化",
        summary="聚焦线下、DMF、手动输入版和暂停检查能力。",
        patterns=(
            "*线下*.py",
            "locators.py",
            "ui_helpers.py",
            "pause_manager.py",
        ),
        starter_queries=(
            "线下自动化 dmf 手动输入版 差异",
            "offline hsbc automation pause_manager",
            "线下脚本走哪些页面元素定位器",
        ),
        questions=(
            "线下标准版、DMF 版、手动输入版分别适合什么场景",
            "暂停检查能力在哪个模块里",
        ),
        related_topics=("50-online-ui-automation", "10-mock-core-flow"),
    ),
    TopicDefinition(
        slug="70-governance-and-planning",
        title="治理规划与需求源文档",
        summary="聚焦短期计划、长期治理、AI 测试方案与需求设计源文件。",
        patterns=(
            "DPU_2MONTH_TEST_PLAN.md",
            "DPU_2MONTH_TEST_PLAN_REPORT.md",
            "DPU_AUTOMATION_AI_TEST_PLAN.md",
            "DPU_LONG_TERM_TEST_GOVERNANCE_REPORT.md",
            "dpu模拟需求文档.docx",
            "*需求文档*.pdf",
        ),
        starter_queries=(
            "长期治理 版本回归 AI 报告",
            "task requirement design document",
            "两个月计划和长期治理的区别",
        ),
        questions=(
            "短期建设和长期治理文档各自负责什么",
            "需求源文档里有哪些可供检索的设计信息",
        ),
        related_topics=("20-metersphere-mockapi", "30-migration-reg-prod"),
    ),
)


def _extract_wordprocessingml_text(data: bytes) -> str | None:
    try:
        with ZipFile(BytesIO(data)) as zf:
            names = zf.namelist()
            xml_members = [
                name
                for name in names
                if name == "word/document.xml"
                or name.startswith("word/header")
                or name.startswith("word/footer")
            ]
            if not xml_members:
                return None

            paragraphs: list[str] = []
            for member in xml_members:
                root = ET.fromstring(zf.read(member))
                for paragraph in root.findall(".//w:p", WORDPROCESSINGML_NS):
                    texts = [
                        node.text.strip()
                        for node in paragraph.findall(".//w:t", WORDPROCESSINGML_NS)
                        if node.text and node.text.strip()
                    ]
                    if texts:
                        paragraphs.append("".join(texts))
            text = "\n".join(paragraphs).strip()
            return text or None
    except Exception:
        return None


def _read_path_text(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None

    if not data:
        return ""

    if is_zipfile(BytesIO(data)):
        office_text = _extract_wordprocessingml_text(data)
        if office_text:
            return office_text
        return None

    for encoding in TEXT_ENCODINGS:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    if path.suffix.lower() in {".py", ".md", ".txt", ".json", ".ini", ".toml", ".yaml", ".yml", ".ps1", ".bat"}:
        return data.decode("utf-8", errors="replace")
    return None


def _extract_python_symbols(text: str) -> list[str]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        symbols = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("class "):
                symbols.append(stripped.split("class ", 1)[1].split("(", 1)[0].split(":", 1)[0].strip())
            elif stripped.startswith("def "):
                symbols.append(stripped.split("def ", 1)[1].split("(", 1)[0].strip())
            if len(symbols) >= 8:
                break
        return symbols

    symbols: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols.append(node.name)
        if len(symbols) >= 8:
            break
    return symbols


def _extract_leading_doc_line(text: str) -> str:
    preview_lines: list[str] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        preview_lines.append(raw_line)
        if len(preview_lines) >= 80:
            break

    preview = "\n".join(preview_lines)
    start_index = -1
    quote = ""
    for candidate in ('"""', "'''"):
        idx = preview.find(candidate)
        if idx != -1 and (start_index == -1 or idx < start_index):
            start_index = idx
            quote = candidate
    if start_index == -1:
        return ""

    end_index = preview.find(quote, start_index + len(quote))
    if end_index == -1:
        return ""

    content = preview[start_index + len(quote):end_index]
    for line in content.splitlines():
        clean = line.strip().lstrip("\ufeff")
        if clean:
            return clean
    return ""


def _summarize_path(project_root: Path, path: Path) -> str:
    rel_path = path.relative_to(project_root).as_posix()

    if path.suffix.lower() == ".pdf":
        return "Binary PDF requirement or design document. Open directly when exact wording or layout matters."

    text = _read_path_text(path)
    if not text:
        return "Unreadable or binary source. Open directly if the exact file is required."

    if path.suffix.lower() == ".py":
        doc = _extract_leading_doc_line(text)
        symbols = _extract_python_symbols(text)
        try:
            module = ast.parse(text)
            module_doc = ast.get_docstring(module)
            if module_doc:
                doc = module_doc.strip().splitlines()[0]
        except SyntaxError:
            pass
        parts = []
        if doc:
            parts.append(doc)
        if symbols:
            parts.append("symbols: " + ", ".join(symbols[:6]))
        return " | ".join(parts)[:320] if parts else "Python module"

    headings = [line.strip() for line in text.splitlines() if line.strip().startswith("#")]
    if headings:
        return " | ".join(headings[:4])[:320]

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return " | ".join(lines[:4])[:320] if lines else rel_path


def _collect_files(project_root: Path, patterns: tuple[str, ...]) -> list[Path]:
    collected: dict[str, Path] = {}
    for pattern in patterns:
        for path in project_root.glob(pattern):
            if not path.is_file():
                continue
            if "node_modules" in {part.lower() for part in path.parts}:
                continue
            collected[path.relative_to(project_root).as_posix()] = path
    return [collected[key] for key in sorted(collected)]


def _render_topic_portal(project_root: Path, definition: TopicDefinition, files: list[Path]) -> str:
    lines = [
        f"# {definition.title}",
        "",
        definition.summary,
        "",
        "## 适合问这些问题",
    ]
    for question in definition.questions:
        lines.append(f"- {question}")

    lines.extend(["", "## 核心入口文件"])
    if not files:
        lines.append("- 当前没有匹配到文件，请先检查项目结构或刷新专题入口。")
    else:
        for path in files:
            rel_path = path.relative_to(project_root).as_posix()
            lines.append(f"- `{rel_path}`: {_summarize_path(project_root, path)}")

    lines.extend(["", "## 快速检索命令"])
    for query in definition.starter_queries:
        lines.append(f"- `& '.\\.venv\\Scripts\\python.exe' -m dpu_rag_mvp search \"{query}\"`")

    lines.extend(["", "## 推荐问法"])
    for query in definition.starter_queries:
        lines.append(f"- {query}")

    if definition.related_topics:
        lines.extend(["", "## 关联主题"])
        for related in definition.related_topics:
            lines.append(f"- `{related}`")

    lines.append("")
    return "\n".join(lines)


def build_topic_portals(project_root: Path, portal_dir: Path) -> list[TopicPortalInfo]:
    portal_dir.mkdir(parents=True, exist_ok=True)

    infos: list[TopicPortalInfo] = []
    expected_files = {"README.md"}
    for definition in TOPIC_DEFINITIONS:
        files = _collect_files(project_root, definition.patterns)
        rel_files = [path.relative_to(project_root).as_posix() for path in files]
        file_name = f"{definition.slug}.md"
        expected_files.add(file_name)
        portal_path = portal_dir / file_name
        portal_text = _render_topic_portal(project_root, definition, files)
        portal_path.write_text(portal_text, encoding="utf-8", newline="\n")
        infos.append(
            TopicPortalInfo(
                slug=definition.slug,
                title=definition.title,
                summary=definition.summary,
                rel_path=portal_path.relative_to(project_root).as_posix(),
                file_count=len(files),
                top_files=rel_files[:8],
                starter_queries=list(definition.starter_queries),
            )
        )

    index_lines = [
        "# DPU 专题检索入口",
        "",
        "这些入口文档会在构建本地 RAG 索引时自动刷新，用来承接 task.md、SOP、迁移脚本、mockapi 和自动化脚本等长上下文。",
        "",
    ]
    for info in infos:
        index_lines.append(
            f"- [{info.title}]({Path(info.rel_path).name})"
            f": {info.summary} | files={info.file_count}"
        )
    index_lines.append("")
    (portal_dir / "README.md").write_text("\n".join(index_lines), encoding="utf-8", newline="\n")

    for existing in portal_dir.glob("*.md"):
        if existing.name not in expected_files:
            existing.unlink()

    return infos
