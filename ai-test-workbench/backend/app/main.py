import csv
import hashlib
import hmac
import io
import json
import secrets
from datetime import datetime, timedelta
from typing import Any

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .database import get_db, init_db
from .dify_client import DifyClient
from .models import (
    AiTask,
    AiIssue,
    AuditLog,
    AuthSession,
    CaseVersion,
    Comment,
    ImportJob,
    KnowledgeDocument,
    Project,
    Release,
    ReviewTask,
    ReviewTaskCase,
    RunCaseResult,
    Suite,
    TestCase,
    TestPlan,
    TestRun,
    User,
    UserCredential,
)
from .schemas import (
    AiTaskOut,
    AiIssueCreate,
    AiIssueOut,
    AuditLogOut,
    CaseVersionOut,
    CommentCreate,
    CommentOut,
    GeneratedCaseSave,
    ImportJobOut,
    KnowledgeDocumentOut,
    LoginRequest,
    LoginResponse,
    PasswordChange,
    ProjectCreate,
    ProjectOut,
    ReviewTaskCreate,
    ReviewTaskCaseOut,
    ReviewTaskOut,
    ReviewTaskUpdate,
    RunCaseResultCreate,
    RunCaseResultOut,
    RunCaseResultUpdate,
    TestCaseCreate,
    TestCaseOut,
    TestCaseUpdate,
    TestPlanCreate,
    TestPlanOut,
    TestPlanUpdate,
    TestRunCreate,
    TestRunOut,
    TestRunUpdate,
    UserCreate,
    UserOut,
    UserUpdate,
)


app = FastAPI(title="TestPilot AI Backend", version="0.2.0")
client = DifyClient()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3010", "http://127.0.0.1:3010"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    project: str = "DPU Financing"
    release: str = "DPU Regression v1.0"
    suite: str = "Financing Flow Regression"
    prompt: str
    output_type: str = "cases"


class ReviewRequest(BaseModel):
    project: str = "DPU Financing"
    release: str = "DPU Regression v1.0"
    suite: str = "Financing Flow Regression"
    content: str
    criteria: list[str] = []


ROLE_PERMISSIONS = {
    "QA Lead": {"write", "manage", "review", "execute", "import_export"},
    "Automation QA": {"write", "execute", "import_export"},
    "API QA": {"write", "execute", "review"},
    "Functional QA": {"write", "execute"},
    "AI Copilot": {"review"},
}


def password_hash(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()


def set_password(db: Session, user: User, password: str) -> None:
    existing = db.query(UserCredential).filter(UserCredential.user_id == user.id).first()
    salt = secrets.token_hex(16)
    credential = existing or UserCredential(user_id=user.id, salt=salt, password_hash="")
    credential.salt = salt
    credential.password_hash = password_hash(password, salt)
    db.add(credential)


def snapshot_case(case: TestCase) -> str:
    return json.dumps(
        {
            "case_key": case.case_key,
            "title": case.title,
            "module": case.module,
            "case_type": case.case_type,
            "priority": case.priority,
            "status": case.status,
            "owner": case.owner,
            "steps": case.steps,
            "expected_result": case.expected_result,
            "suite_id": case.suite_id,
        },
        ensure_ascii=False,
    )


def save_case_version(db: Session, case: TestCase, actor: str, summary: str) -> None:
    latest = db.query(CaseVersion).filter(CaseVersion.case_id == case.id).order_by(CaseVersion.version.desc()).first()
    db.add(
        CaseVersion(
            case_id=case.id,
            version=(latest.version + 1) if latest else 1,
            actor=actor,
            change_summary=summary,
            snapshot=snapshot_case(case),
        )
    )


def recalculate_run_totals(db: Session, run_id: int) -> None:
    run = db.get(TestRun, run_id)
    if not run:
        return
    results = db.query(RunCaseResult).filter(RunCaseResult.run_id == run_id).all()
    run.total = len(results)
    run.passed = sum(1 for item in results if item.status == "Passed")
    run.failed = sum(1 for item in results if item.status == "Failed")
    run.blocked = sum(1 for item in results if item.status == "Blocked")
    run.status = "Complete" if results and all(item.status in {"Passed", "Failed", "Blocked", "Skipped"} for item in results) else run.status
    run.updated_at = datetime.utcnow()


def ensure_run_results(db: Session, run: TestRun) -> None:
    existing_case_ids = {
        item.case_id for item in db.query(RunCaseResult).filter(RunCaseResult.run_id == run.id).all()
    }
    cases = db.query(TestCase).order_by(TestCase.id).all()
    for case in cases:
        if case.id not in existing_case_ids:
            db.add(RunCaseResult(run_id=run.id, case_id=case.id, status="Not Run", executor=run.assignee))
    db.flush()
    recalculate_run_totals(db, run.id)


def record_audit(
    db: Session,
    action: str,
    entity_type: str,
    entity_id: str,
    summary: str,
    actor: str = "Codex QA",
) -> None:
    db.add(AuditLog(actor=actor, action=action, entity_type=entity_type, entity_id=entity_id, summary=summary))


def current_user(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing auth token")
    token = authorization.removeprefix("Bearer ").strip()
    session = db.query(AuthSession).filter(AuthSession.token == token).first()
    if not session or session.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="invalid or expired token")
    user = db.get(User, session.user_id)
    if not user or user.active != "yes":
        raise HTTPException(status_code=403, detail="inactive user")
    return user


def optional_user(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> User:
    if authorization and authorization.startswith("Bearer "):
        return current_user(db, authorization)
    fallback = db.query(User).filter(User.username == "maya").first()
    if not fallback:
        raise HTTPException(status_code=401, detail="no active user")
    return fallback


def require_permission(permission: str):
    def checker(user: User = Depends(optional_user)) -> User:
        permissions = ROLE_PERMISSIONS.get(user.role, {"write"})
        if permission not in permissions and "manage" not in permissions:
            raise HTTPException(status_code=403, detail=f"{user.role} cannot {permission}")
        return user

    return checker


def seed_database() -> None:
    db = next(get_db())
    try:
        if not db.query(User).first():
            users = [
                User(username="maya", display_name="Maya Chen", role="QA Lead"),
                User(username="alex", display_name="Alex Li", role="Automation QA"),
                User(username="nora", display_name="Nora Wang", role="API QA"),
                User(username="ken", display_name="Ken Zhang", role="Functional QA"),
                User(username="codex", display_name="Codex QA", role="AI Copilot"),
            ]
            db.add_all(users)
            db.flush()
            for user in users:
                set_password(db, user, "testpilot123")
            db.commit()
        else:
            for user in db.query(User).all():
                if not db.query(UserCredential).filter(UserCredential.user_id == user.id).first():
                    set_password(db, user, "testpilot123")
            db.commit()

        project = db.query(Project).first()
        if not project:
            project = Project(name="DPU Financing", description="DPU financing QA workbench")
            db.add(project)
            db.flush()
            release = Release(project_id=project.id, name="DPU Regression v1.0")
            suite = Suite(project_id=project.id, name="Financing Flow Regression", parent_name="DPU")
            db.add_all([release, suite])
            db.flush()
            seed_cases = [
                TestCase(
                    case_key="TC-DPU-001",
                    title="New user completes registration and starts financing application",
                    module="Registration",
                    case_type="Functional",
                    priority="P0",
                    status="Ready",
                    owner="Maya",
                    suite_id=suite.id,
                ),
                TestCase(
                    case_key="TC-DPU-014",
                    title="PSP verification succeeds after timeout retry",
                    module="PSP Verification",
                    case_type="Negative",
                    priority="P0",
                    status="Needs work",
                    owner="Alex",
                    suite_id=suite.id,
                ),
                TestCase(
                    case_key="TC-DPU-022",
                    title="Shop information syncs after SP authorization",
                    module="SP Authorization",
                    case_type="Boundary",
                    priority="P1",
                    status="Draft",
                    owner="Nora",
                    suite_id=suite.id,
                ),
            ]
            db.add_all(seed_cases)
            db.flush()
            for case in seed_cases:
                save_case_version(db, case, "system", "Seeded baseline case")
            record_audit(db, "seed", "project", str(project.id), "Initialized DPU workspace.", actor="system")

        if not db.query(TestPlan).first():
            plan = TestPlan(
                name="DPU main flow regression",
                scope="Registration, SP authorization, PSP, E-sign, drawdown, repayment callback",
                owner="Maya",
                status="Running",
                risk="Medium",
            )
            db.add(plan)
            db.flush()
            db.add_all(
                [
                    TestRun(plan_id=plan.id, name="DPU regression round 1", cycle="Round 1", assignee="Alex", status="Running", passed=18, failed=3, blocked=2, total=32),
                    TestRun(plan_id=plan.id, name="DPU regression round 2", cycle="Round 2", assignee="Nora", status="Not started", total=32),
                ]
            )
            review_task = ReviewTask(
                title="PSP regression case review",
                submitter="Alex",
                reviewer="Maya",
                status="Needs changes",
                score=82,
                risk="High",
                case_count=18,
                summary="PSP timeout retry and callback coverage need stronger observable assertions.",
            )
            db.add(review_task)
            record_audit(db, "seed", "team_workflow", str(plan.id), "Seeded plan, runs, and review queue.", actor="system")
            db.flush()
            for run in db.query(TestRun).all():
                ensure_run_results(db, run)
            review_task_case_ids = [case.id for case in db.query(TestCase).limit(3).all()]
            for case_id in review_task_case_ids:
                db.add(ReviewTaskCase(review_task_id=review_task.id, case_id=case_id))
        else:
            for run in db.query(TestRun).all():
                ensure_run_results(db, run)
        db.commit()
    finally:
        db.close()


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    seed_database()


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "dify_configured": client.configured,
        "dataset_configured": bool(client.dataset_id),
        "generate_workflow_configured": bool(client.generate_key),
        "review_workflow_configured": bool(client.review_key),
        "model_configured": client.model_configured,
        "model_name": client.model_name if client.model_configured else None,
    }


@app.post("/api/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    user = db.query(User).filter(User.username == payload.username, User.active == "yes").first()
    if not user:
        raise HTTPException(status_code=401, detail="invalid username or password")
    credential = db.query(UserCredential).filter(UserCredential.user_id == user.id).first()
    if not credential or not hmac.compare_digest(credential.password_hash, password_hash(payload.password, credential.salt)):
        raise HTTPException(status_code=401, detail="invalid username or password")
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(token=token, user_id=user.id, expires_at=datetime.utcnow() + timedelta(days=7)))
    record_audit(db, "login", "user", str(user.id), f"{user.display_name} logged in.", actor=user.display_name)
    db.commit()
    db.refresh(user)
    return {"token": token, "user": user}


@app.get("/api/auth/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> User:
    return user


@app.get("/api/projects", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)) -> list[Project]:
    return db.query(Project).order_by(Project.id).all()


@app.post("/api/projects", response_model=ProjectOut)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("manage")),
) -> Project:
    project = Project(name=payload.name, description=payload.description)
    db.add(project)
    db.flush()
    record_audit(db, "create", "project", str(project.id), f"Created project {project.name}.", actor=user.display_name)
    db.commit()
    db.refresh(project)
    return project


@app.get("/api/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)) -> list[User]:
    return db.query(User).order_by(User.id).all()


@app.post("/api/users", response_model=UserOut)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("manage")),
) -> User:
    new_user = User(**payload.model_dump())
    db.add(new_user)
    db.flush()
    set_password(db, new_user, "testpilot123")
    record_audit(db, "create", "user", str(new_user.id), f"Added team member {new_user.display_name}.", actor=user.display_name)
    db.commit()
    db.refresh(new_user)
    return new_user


@app.patch("/api/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("manage")),
) -> User:
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="user not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(target, key, value)
    record_audit(db, "update", "user", str(target.id), f"Updated team member {target.display_name}.", actor=user.display_name)
    db.commit()
    db.refresh(target)
    return target


@app.post("/api/auth/change-password")
def change_password(payload: PasswordChange, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    credential = db.query(UserCredential).filter(UserCredential.user_id == user.id).first()
    if not credential or not hmac.compare_digest(credential.password_hash, password_hash(payload.old_password, credential.salt)):
        raise HTTPException(status_code=400, detail="old password is incorrect")
    set_password(db, user, payload.new_password)
    record_audit(db, "change_password", "user", str(user.id), f"{user.display_name} changed password.", actor=user.display_name)
    db.commit()
    return {"ok": True}


@app.get("/api/cases", response_model=list[TestCaseOut])
def list_cases(
    q: str = "",
    module: str = "",
    priority: str = "",
    status: str = "",
    owner: str = "",
    db: Session = Depends(get_db),
) -> list[TestCase]:
    query = db.query(TestCase)
    if q:
        pattern = f"%{q}%"
        query = query.filter(or_(TestCase.case_key.ilike(pattern), TestCase.title.ilike(pattern), TestCase.module.ilike(pattern)))
    if module:
        query = query.filter(TestCase.module == module)
    if priority:
        query = query.filter(TestCase.priority == priority)
    if status:
        query = query.filter(TestCase.status == status)
    if owner:
        query = query.filter(TestCase.owner == owner)
    return query.order_by(TestCase.id).all()


@app.post("/api/cases", response_model=TestCaseOut)
def create_case(
    payload: TestCaseCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("write")),
) -> TestCase:
    case = TestCase(**payload.model_dump())
    db.add(case)
    db.flush()
    save_case_version(db, case, user.display_name, "Created case")
    record_audit(db, "create", "test_case", str(case.id), f"Created {case.case_key}: {case.title}.", actor=user.display_name)
    db.commit()
    db.refresh(case)
    return case


@app.patch("/api/cases/{case_id}", response_model=TestCaseOut)
def update_case(
    case_id: int,
    payload: TestCaseUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("write")),
) -> TestCase:
    case = db.get(TestCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="case not found")
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(case, key, value)
    case.updated_at = datetime.utcnow()
    save_case_version(db, case, user.display_name, f"Updated fields: {', '.join(changes.keys())}")
    record_audit(db, "update", "test_case", str(case.id), f"Updated {case.case_key}: {case.title}.", actor=user.display_name)
    db.commit()
    db.refresh(case)
    return case


@app.delete("/api/cases/{case_id}")
def delete_case(
    case_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("write")),
) -> dict[str, Any]:
    case = db.get(TestCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="case not found")
    case_key = case.case_key
    title = case.title
    db.delete(case)
    record_audit(db, "delete", "test_case", str(case_id), f"Deleted {case_key}: {title}.", actor=user.display_name)
    db.commit()
    return {"ok": True}


@app.get("/api/cases/export")
def export_cases(db: Session = Depends(get_db), user: User = Depends(require_permission("import_export"))) -> Response:
    rows = db.query(TestCase).order_by(TestCase.id).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["case_key", "title", "module", "case_type", "priority", "status", "owner", "steps", "expected_result"])
    for row in rows:
        writer.writerow([row.case_key, row.title, row.module, row.case_type, row.priority, row.status, row.owner, row.steps, row.expected_result])
    record_audit(db, "export", "test_case", "all", f"Exported {len(rows)} test cases.", actor=user.display_name)
    db.commit()
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=test_cases.csv"},
    )


@app.post("/api/cases/import")
async def import_cases(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("import_export")),
) -> dict[str, Any]:
    text = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    imported = 0
    updated = 0
    failed = 0
    errors: list[dict[str, Any]] = []
    for row in reader:
        case_key = (row.get("case_key") or "").strip()
        title = (row.get("title") or "").strip()
        if not case_key or not title:
            failed += 1
            errors.append({"row": reader.line_num, "error": "case_key and title are required"})
            continue
        case = db.query(TestCase).filter(TestCase.case_key == case_key).first()
        payload = {
            "title": title,
            "module": row.get("module") or "",
            "case_type": row.get("case_type") or "Functional",
            "priority": row.get("priority") or "P1",
            "status": row.get("status") or "Draft",
            "owner": row.get("owner") or "",
            "steps": row.get("steps") or "",
            "expected_result": row.get("expected_result") or "",
        }
        if case:
            for key, value in payload.items():
                setattr(case, key, value)
            case.updated_at = datetime.utcnow()
            updated += 1
            save_case_version(db, case, user.display_name, "Imported CSV update")
        else:
            case = TestCase(case_key=case_key, **payload)
            db.add(case)
            db.flush()
            imported += 1
            save_case_version(db, case, user.display_name, "Imported CSV create")
    job = ImportJob(
        filename=file.filename or "csv",
        status="Completed with errors" if failed else "Completed",
        imported=imported,
        updated=updated,
        failed=failed,
        error_report=json.dumps(errors, ensure_ascii=False),
        created_by=user.display_name,
    )
    db.add(job)
    record_audit(db, "import", "test_case", file.filename or "csv", f"Imported {imported}, updated {updated}, failed {failed} test cases.", actor=user.display_name)
    db.commit()
    return {"ok": True, "imported": imported, "updated": updated, "failed": failed, "errors": errors, "job_id": job.id}


@app.get("/api/cases/import-template")
def import_template() -> Response:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["case_key", "title", "module", "case_type", "priority", "status", "owner", "steps", "expected_result"])
    writer.writerow(["TC-DPU-NEW-001", "PSP timeout retry should preserve application status", "PSP Verification", "Negative", "P0", "Draft", "Maya", "1. Trigger PSP timeout\n2. Retry PSP verification", "Application status remains recoverable and webhook is recorded"])
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=test_cases_import_template.csv"},
    )


@app.get("/api/import-jobs", response_model=list[ImportJobOut])
def list_import_jobs(db: Session = Depends(get_db)) -> list[ImportJob]:
    return db.query(ImportJob).order_by(ImportJob.id.desc()).limit(50).all()


@app.get("/api/cases/{case_id}/versions", response_model=list[CaseVersionOut])
def list_case_versions(case_id: int, db: Session = Depends(get_db)) -> list[CaseVersion]:
    return db.query(CaseVersion).filter(CaseVersion.case_id == case_id).order_by(CaseVersion.version.desc()).all()


@app.get("/api/plans", response_model=list[TestPlanOut])
def list_plans(db: Session = Depends(get_db)) -> list[TestPlan]:
    return db.query(TestPlan).order_by(TestPlan.id.desc()).all()


@app.post("/api/plans", response_model=TestPlanOut)
def create_plan(payload: TestPlanCreate, db: Session = Depends(get_db), user: User = Depends(require_permission("write"))) -> TestPlan:
    plan = TestPlan(**payload.model_dump())
    db.add(plan)
    db.flush()
    record_audit(db, "create", "test_plan", str(plan.id), f"Created plan {plan.name}.", actor=user.display_name)
    db.commit()
    db.refresh(plan)
    return plan


@app.patch("/api/plans/{plan_id}", response_model=TestPlanOut)
def update_plan(plan_id: int, payload: TestPlanUpdate, db: Session = Depends(get_db), user: User = Depends(require_permission("write"))) -> TestPlan:
    plan = db.get(TestPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="plan not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(plan, key, value)
    plan.updated_at = datetime.utcnow()
    record_audit(db, "update", "test_plan", str(plan.id), f"Updated plan {plan.name}.", actor=user.display_name)
    db.commit()
    db.refresh(plan)
    return plan


@app.get("/api/runs", response_model=list[TestRunOut])
def list_runs(plan_id: int | None = None, db: Session = Depends(get_db)) -> list[TestRun]:
    query = db.query(TestRun)
    if plan_id:
        query = query.filter(TestRun.plan_id == plan_id)
    return query.order_by(TestRun.id.desc()).all()


@app.post("/api/runs", response_model=TestRunOut)
def create_run(payload: TestRunCreate, db: Session = Depends(get_db), user: User = Depends(require_permission("execute"))) -> TestRun:
    run = TestRun(**payload.model_dump())
    db.add(run)
    db.flush()
    record_audit(db, "create", "test_run", str(run.id), f"Created run {run.name}.", actor=user.display_name)
    db.commit()
    db.refresh(run)
    return run


@app.patch("/api/runs/{run_id}", response_model=TestRunOut)
def update_run(run_id: int, payload: TestRunUpdate, db: Session = Depends(get_db), user: User = Depends(require_permission("execute"))) -> TestRun:
    run = db.get(TestRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(run, key, value)
    run.updated_at = datetime.utcnow()
    record_audit(db, "update", "test_run", str(run.id), f"Updated run {run.name}.", actor=user.display_name)
    db.commit()
    db.refresh(run)
    return run


@app.get("/api/run-results", response_model=list[RunCaseResultOut])
def list_run_results(run_id: int, db: Session = Depends(get_db)) -> list[RunCaseResult]:
    run = db.get(TestRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    ensure_run_results(db, run)
    db.commit()
    return db.query(RunCaseResult).filter(RunCaseResult.run_id == run_id).order_by(RunCaseResult.id).all()


@app.post("/api/run-results", response_model=RunCaseResultOut)
def create_run_result(payload: RunCaseResultCreate, db: Session = Depends(get_db), user: User = Depends(require_permission("execute"))) -> RunCaseResult:
    existing = db.query(RunCaseResult).filter(RunCaseResult.run_id == payload.run_id, RunCaseResult.case_id == payload.case_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="run case result already exists")
    result = RunCaseResult(**payload.model_dump())
    if result.status != "Not Run":
        result.executed_at = datetime.utcnow()
        result.executor = result.executor or user.display_name
    db.add(result)
    db.flush()
    recalculate_run_totals(db, result.run_id)
    record_audit(db, "create", "run_case_result", str(result.id), f"Added case {result.case_id} to run {result.run_id}.", actor=user.display_name)
    db.commit()
    db.refresh(result)
    return result


@app.patch("/api/run-results/{result_id}", response_model=RunCaseResultOut)
def update_run_result(result_id: int, payload: RunCaseResultUpdate, db: Session = Depends(get_db), user: User = Depends(require_permission("execute"))) -> RunCaseResult:
    result = db.get(RunCaseResult, result_id)
    if not result:
        raise HTTPException(status_code=404, detail="run result not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(result, key, value)
    if payload.status and payload.status != "Not Run":
        result.executed_at = datetime.utcnow()
        result.executor = result.executor or user.display_name
    result.updated_at = datetime.utcnow()
    recalculate_run_totals(db, result.run_id)
    record_audit(db, "execute", "run_case_result", str(result.id), f"Set case {result.case_id} in run {result.run_id} to {result.status}.", actor=user.display_name)
    db.commit()
    db.refresh(result)
    return result


@app.get("/api/review-tasks", response_model=list[ReviewTaskOut])
def list_review_tasks(db: Session = Depends(get_db)) -> list[ReviewTask]:
    return db.query(ReviewTask).order_by(ReviewTask.id.desc()).all()


@app.post("/api/review-tasks", response_model=ReviewTaskOut)
def create_review_task(payload: ReviewTaskCreate, db: Session = Depends(get_db), user: User = Depends(require_permission("review"))) -> ReviewTask:
    data = payload.model_dump()
    case_ids = data.pop("case_ids", [])
    task = ReviewTask(**data)
    if case_ids:
        task.case_count = len(case_ids)
    db.add(task)
    db.flush()
    for case_id in case_ids:
        db.add(ReviewTaskCase(review_task_id=task.id, case_id=case_id))
    record_audit(db, "create", "review_task", str(task.id), f"Created review task {task.title}.", actor=user.display_name)
    db.commit()
    db.refresh(task)
    return task


@app.patch("/api/review-tasks/{task_id}", response_model=ReviewTaskOut)
def update_review_task(task_id: int, payload: ReviewTaskUpdate, db: Session = Depends(get_db), user: User = Depends(require_permission("review"))) -> ReviewTask:
    task = db.get(ReviewTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="review task not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, key, value)
    task.updated_at = datetime.utcnow()
    record_audit(db, "update", "review_task", str(task.id), f"Updated review task {task.title} to {task.status}.", actor=user.display_name)
    db.commit()
    db.refresh(task)
    return task


@app.get("/api/review-tasks/{task_id}/cases", response_model=list[ReviewTaskCaseOut])
def list_review_task_cases(task_id: int, db: Session = Depends(get_db)) -> list[ReviewTaskCase]:
    return db.query(ReviewTaskCase).filter(ReviewTaskCase.review_task_id == task_id).order_by(ReviewTaskCase.id).all()


@app.post("/api/review-tasks/{task_id}/cases", response_model=ReviewTaskCaseOut)
def add_review_task_case(task_id: int, case_id: int, db: Session = Depends(get_db), user: User = Depends(require_permission("review"))) -> ReviewTaskCase:
    task = db.get(ReviewTask, task_id)
    case = db.get(TestCase, case_id)
    if not task or not case:
        raise HTTPException(status_code=404, detail="review task or case not found")
    existing = db.query(ReviewTaskCase).filter(ReviewTaskCase.review_task_id == task_id, ReviewTaskCase.case_id == case_id).first()
    if existing:
        return existing
    link = ReviewTaskCase(review_task_id=task_id, case_id=case_id)
    db.add(link)
    task.case_count += 1
    record_audit(db, "link", "review_task_case", str(task_id), f"Linked {case.case_key} to review task {task.title}.", actor=user.display_name)
    db.commit()
    db.refresh(link)
    return link


@app.get("/api/comments", response_model=list[CommentOut])
def list_comments(entity_type: str = "", entity_id: str = "", db: Session = Depends(get_db)) -> list[Comment]:
    query = db.query(Comment)
    if entity_type:
        query = query.filter(Comment.entity_type == entity_type)
    if entity_id:
        query = query.filter(Comment.entity_id == entity_id)
    return query.order_by(Comment.id.desc()).limit(100).all()


@app.post("/api/comments", response_model=CommentOut)
def create_comment(payload: CommentCreate, db: Session = Depends(get_db), user: User = Depends(require_permission("write"))) -> Comment:
    comment = Comment(entity_type=payload.entity_type, entity_id=payload.entity_id, author=user.display_name, body=payload.body)
    db.add(comment)
    db.flush()
    record_audit(db, "comment", payload.entity_type, payload.entity_id, f"Commented on {payload.entity_type} {payload.entity_id}.", actor=user.display_name)
    db.commit()
    db.refresh(comment)
    return comment


@app.get("/api/documents", response_model=list[KnowledgeDocumentOut])
def list_documents(db: Session = Depends(get_db)) -> list[KnowledgeDocument]:
    return db.query(KnowledgeDocument).order_by(KnowledgeDocument.id.desc()).all()


@app.get("/api/tasks", response_model=list[AiTaskOut])
def list_tasks(db: Session = Depends(get_db)) -> list[AiTask]:
    return db.query(AiTask).order_by(AiTask.id.desc()).all()


@app.post("/api/ai/generated-cases/save", response_model=list[TestCaseOut])
def save_generated_cases(payload: GeneratedCaseSave, db: Session = Depends(get_db), user: User = Depends(require_permission("write"))) -> list[TestCase]:
    saved: list[TestCase] = []
    for case_payload in payload.cases:
        existing = db.query(TestCase).filter(TestCase.case_key == case_payload.case_key).first()
        if existing:
            continue
        case = TestCase(**case_payload.model_dump())
        db.add(case)
        db.flush()
        save_case_version(db, case, user.display_name, f"Saved from AI task {payload.task_id or '-'}")
        saved.append(case)
    if payload.task_id:
        task = db.get(AiTask, payload.task_id)
        if task:
            task.status = "saved"
    record_audit(db, "save_generated_cases", "ai_task", str(payload.task_id or ""), f"Saved {len(saved)} generated cases.", actor=user.display_name)
    db.commit()
    for case in saved:
        db.refresh(case)
    return saved


@app.post("/api/ai/issues", response_model=AiIssueOut)
def create_ai_issue(payload: AiIssueCreate, db: Session = Depends(get_db), user: User = Depends(require_permission("review"))) -> AiIssue:
    issue = AiIssue(**payload.model_dump())
    db.add(issue)
    db.flush()
    record_audit(db, "create", "ai_issue", str(issue.id), f"Created AI issue {issue.title}.", actor=user.display_name)
    db.commit()
    db.refresh(issue)
    return issue


@app.get("/api/ai/issues", response_model=list[AiIssueOut])
def list_ai_issues(db: Session = Depends(get_db)) -> list[AiIssue]:
    return db.query(AiIssue).order_by(AiIssue.id.desc()).limit(100).all()


@app.get("/api/audit-logs", response_model=list[AuditLogOut])
def list_audit_logs(db: Session = Depends(get_db)) -> list[AuditLog]:
    return db.query(AuditLog).order_by(AuditLog.id.desc()).limit(200).all()


@app.post("/api/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    project: str = Form("DPU Financing"),
    release: str = Form("DPU Regression v1.0"),
    suite: str = Form("Financing Flow Regression"),
    source_type: str = Form("Requirement"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("write")),
) -> dict[str, Any]:
    content = await file.read()
    metadata = {"project": project, "release": release, "suite": suite, "source_type": source_type, "size": len(content)}
    result = await client.upload_document(file.filename or "document", content, metadata)
    document = KnowledgeDocument(
        filename=file.filename or "document",
        source_type=source_type,
        project=project,
        release=release,
        suite=suite,
        size=len(content),
        status=str(result.get("status", "queued")),
        provider=str(result.get("provider", "dify")),
        provider_document_id=str(result.get("document_id", "")),
    )
    db.add(document)
    db.flush()
    record_audit(db, "upload", "knowledge_document", str(document.id), f"Uploaded {document.filename}.", actor=user.display_name)
    db.commit()
    db.refresh(document)
    return {"ok": True, "filename": file.filename, "metadata": metadata, "document_id": document.id, "dify": result}


@app.post("/api/generate")
async def generate_tests(payload: GenerateRequest, db: Session = Depends(get_db), user: User = Depends(require_permission("write"))) -> dict[str, Any]:
    result = await client.run_workflow("generate", payload.model_dump())
    output = result.get("output", {})
    output_text = output.get("content") or output.get("summary") or str(output)
    task = AiTask(
        task_type="generate",
        project=payload.project,
        release=payload.release,
        suite=payload.suite,
        input_text=payload.prompt,
        output_text=output_text,
        status=str(result.get("status", "succeeded")),
        provider=str(result.get("provider", "")),
        model=str(result.get("model", "")),
    )
    db.add(task)
    db.flush()
    record_audit(db, "generate", "ai_task", str(task.id), f"Generated {payload.output_type}.", actor=user.display_name)
    db.commit()
    db.refresh(task)
    return {"ok": True, "task": "generate", "task_id": task.id, "dify": result}


@app.post("/api/review")
async def review_cases(payload: ReviewRequest, db: Session = Depends(get_db), user: User = Depends(require_permission("review"))) -> dict[str, Any]:
    result = await client.run_workflow("review", payload.model_dump())
    output = result.get("output", {})
    output_text = output.get("content") or str(output)
    task = AiTask(
        task_type="review",
        project=payload.project,
        release=payload.release,
        suite=payload.suite,
        input_text=payload.content,
        output_text=output_text,
        status=str(result.get("status", "succeeded")),
        provider=str(result.get("provider", "")),
        model=str(result.get("model", "")),
    )
    db.add(task)
    db.flush()
    record_audit(db, "review", "ai_task", str(task.id), f"Reviewed cases for {payload.suite}.", actor=user.display_name)
    db.commit()
    db.refresh(task)
    return {"ok": True, "task": "review", "task_id": task.id, "dify": result}
