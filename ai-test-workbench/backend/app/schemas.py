from datetime import datetime

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: "UserOut"


class ProjectCreate(BaseModel):
    name: str
    description: str = ""


class ProjectOut(ProjectCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    username: str
    display_name: str
    role: str = "tester"
    active: str = "yes"


class UserUpdate(BaseModel):
    display_name: str | None = None
    role: str | None = None
    active: str | None = None


class PasswordChange(BaseModel):
    old_password: str
    new_password: str


class UserOut(UserCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class TestCaseCreate(BaseModel):
    case_key: str
    title: str
    module: str = ""
    case_type: str = "Functional"
    priority: str = "P1"
    status: str = "Draft"
    owner: str = ""
    steps: str = ""
    expected_result: str = ""
    suite_id: int | None = None


class TestCaseUpdate(BaseModel):
    title: str | None = None
    module: str | None = None
    case_type: str | None = None
    priority: str | None = None
    status: str | None = None
    owner: str | None = None
    steps: str | None = None
    expected_result: str | None = None
    suite_id: int | None = None


class TestCaseOut(TestCaseCreate):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TestPlanCreate(BaseModel):
    name: str
    project: str = "DPU Financing"
    release: str = "DPU Regression v1.0"
    scope: str = ""
    owner: str = ""
    status: str = "Draft"
    risk: str = "Medium"


class TestPlanUpdate(BaseModel):
    name: str | None = None
    scope: str | None = None
    owner: str | None = None
    status: str | None = None
    risk: str | None = None


class TestPlanOut(TestPlanCreate):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TestRunCreate(BaseModel):
    plan_id: int
    name: str
    cycle: str = "Round 1"
    assignee: str = ""
    status: str = "Not started"
    passed: int = 0
    failed: int = 0
    blocked: int = 0
    total: int = 0


class TestRunUpdate(BaseModel):
    name: str | None = None
    cycle: str | None = None
    assignee: str | None = None
    status: str | None = None
    passed: int | None = None
    failed: int | None = None
    blocked: int | None = None
    total: int | None = None


class TestRunOut(TestRunCreate):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RunCaseResultCreate(BaseModel):
    run_id: int
    case_id: int
    status: str = "Not Run"
    executor: str = ""
    actual_result: str = ""
    defect_url: str = ""


class RunCaseResultUpdate(BaseModel):
    status: str | None = None
    executor: str | None = None
    actual_result: str | None = None
    defect_url: str | None = None


class RunCaseResultOut(RunCaseResultCreate):
    id: int
    executed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ReviewTaskCreate(BaseModel):
    title: str
    submitter: str = ""
    reviewer: str = ""
    status: str = "Submitted"
    score: int = 0
    risk: str = "Medium"
    case_count: int = 0
    summary: str = ""
    case_ids: list[int] = []


class ReviewTaskUpdate(BaseModel):
    title: str | None = None
    reviewer: str | None = None
    status: str | None = None
    score: int | None = None
    risk: str | None = None
    case_count: int | None = None
    summary: str | None = None


class ReviewTaskOut(ReviewTaskCreate):
    id: int
    created_at: datetime
    updated_at: datetime
    case_ids: list[int] = []

    class Config:
        from_attributes = True


class ReviewTaskCaseOut(BaseModel):
    id: int
    review_task_id: int
    case_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class CommentCreate(BaseModel):
    entity_type: str
    entity_id: str
    body: str


class CommentOut(CommentCreate):
    id: int
    author: str
    created_at: datetime

    class Config:
        from_attributes = True


class CaseVersionOut(BaseModel):
    id: int
    case_id: int
    version: int
    actor: str
    change_summary: str
    snapshot: str
    created_at: datetime

    class Config:
        from_attributes = True


class KnowledgeDocumentOut(BaseModel):
    id: int
    filename: str
    source_type: str
    project: str
    release: str
    suite: str
    size: int
    status: str
    provider: str
    provider_document_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class AiTaskOut(BaseModel):
    id: int
    task_type: str
    project: str
    release: str
    suite: str
    input_text: str
    output_text: str
    status: str
    provider: str
    model: str
    created_at: datetime

    class Config:
        from_attributes = True


class AiIssueCreate(BaseModel):
    task_id: int
    title: str
    severity: str = "Medium"
    recommendation: str = ""


class AiIssueOut(AiIssueCreate):
    id: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class GeneratedCaseSave(BaseModel):
    task_id: int | None = None
    cases: list[TestCaseCreate]


class ImportJobOut(BaseModel):
    id: int
    filename: str
    status: str
    imported: int
    updated: int
    failed: int
    error_report: str
    created_by: str
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogOut(BaseModel):
    id: int
    actor: str
    action: str
    entity_type: str
    entity_id: str
    summary: str
    created_at: datetime

    class Config:
        from_attributes = True
