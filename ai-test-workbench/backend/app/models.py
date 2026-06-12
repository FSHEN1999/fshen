from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    releases: Mapped[list["Release"]] = relationship(back_populates="project")
    suites: Mapped[list["Suite"]] = relationship(back_populates="project")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(80), default="tester")
    active: Mapped[str] = mapped_column(String(20), default="yes")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UserCredential(Base):
    __tablename__ = "user_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    salt: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    token: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Release(Base):
    __tablename__ = "releases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String(200), index=True)
    status: Mapped[str] = mapped_column(String(50), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped[Project] = relationship(back_populates="releases")


class Suite(Base):
    __tablename__ = "suites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String(200), index=True)
    parent_name: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped[Project] = relationship(back_populates="suites")
    cases: Mapped[list["TestCase"]] = relationship(back_populates="suite")


class TestCase(Base):
    __tablename__ = "test_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    case_key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500))
    module: Mapped[str] = mapped_column(String(200), default="")
    case_type: Mapped[str] = mapped_column(String(80), default="Functional")
    priority: Mapped[str] = mapped_column(String(20), default="P1")
    status: Mapped[str] = mapped_column(String(80), default="Draft")
    owner: Mapped[str] = mapped_column(String(120), default="")
    steps: Mapped[str] = mapped_column(Text, default="")
    expected_result: Mapped[str] = mapped_column(Text, default="")
    suite_id: Mapped[int | None] = mapped_column(ForeignKey("suites.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    suite: Mapped[Suite | None] = relationship(back_populates="cases")


class TestPlan(Base):
    __tablename__ = "test_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(240), index=True)
    project: Mapped[str] = mapped_column(String(200), default="DPU Financing")
    release: Mapped[str] = mapped_column(String(200), default="DPU Regression v1.0")
    scope: Mapped[str] = mapped_column(Text, default="")
    owner: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(80), default="Draft")
    risk: Mapped[str] = mapped_column(String(80), default="Medium")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TestRun(Base):
    __tablename__ = "test_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("test_plans.id"), index=True)
    name: Mapped[str] = mapped_column(String(240), index=True)
    cycle: Mapped[str] = mapped_column(String(120), default="Round 1")
    assignee: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(80), default="Not started")
    passed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    blocked: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RunCaseResult(Base):
    __tablename__ = "run_case_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("test_runs.id"), index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id"), index=True)
    status: Mapped[str] = mapped_column(String(80), default="Not Run", index=True)
    executor: Mapped[str] = mapped_column(String(120), default="")
    actual_result: Mapped[str] = mapped_column(Text, default="")
    defect_url: Mapped[str] = mapped_column(String(500), default="")
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ReviewTask(Base):
    __tablename__ = "review_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(240), index=True)
    submitter: Mapped[str] = mapped_column(String(120), default="")
    reviewer: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(80), default="Submitted")
    score: Mapped[int] = mapped_column(Integer, default=0)
    risk: Mapped[str] = mapped_column(String(80), default="Medium")
    case_count: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ReviewTaskCase(Base):
    __tablename__ = "review_task_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    review_task_id: Mapped[int] = mapped_column(ForeignKey("review_tasks.id"), index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(120), index=True)
    entity_id: Mapped[str] = mapped_column(String(120), index=True)
    author: Mapped[str] = mapped_column(String(120), default="")
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CaseVersion(Base):
    __tablename__ = "case_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    actor: Mapped[str] = mapped_column(String(120), default="")
    change_summary: Mapped[str] = mapped_column(Text, default="")
    snapshot: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(80), default="created")
    imported: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    error_report: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AiIssue(Base):
    __tablename__ = "ai_issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("ai_tasks.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    severity: Mapped[str] = mapped_column(String(80), default="Medium")
    status: Mapped[str] = mapped_column(String(80), default="Open")
    recommendation: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String(500))
    source_type: Mapped[str] = mapped_column(String(120), default="Requirement")
    project: Mapped[str] = mapped_column(String(200), default="DPU Financing")
    release: Mapped[str] = mapped_column(String(200), default="DPU Regression v1.0")
    suite: Mapped[str] = mapped_column(String(200), default="Financing Flow Regression")
    size: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(80), default="queued")
    provider: Mapped[str] = mapped_column(String(80), default="")
    provider_document_id: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AiTask(Base):
    __tablename__ = "ai_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_type: Mapped[str] = mapped_column(String(80), index=True)
    project: Mapped[str] = mapped_column(String(200), default="DPU Financing")
    release: Mapped[str] = mapped_column(String(200), default="DPU Regression v1.0")
    suite: Mapped[str] = mapped_column(String(200), default="Financing Flow Regression")
    input_text: Mapped[str] = mapped_column(Text, default="")
    output_text: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(80), default="created")
    provider: Mapped[str] = mapped_column(String(80), default="")
    model: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    actor: Mapped[str] = mapped_column(String(120), default="system", index=True)
    action: Mapped[str] = mapped_column(String(120), index=True)
    entity_type: Mapped[str] = mapped_column(String(120), index=True)
    entity_id: Mapped[str] = mapped_column(String(120), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
