"use client";

import {
  Bot,
  BrainCircuit,
  ClipboardCheck,
  Download,
  FileStack,
  FileText,
  FolderTree,
  History,
  Languages,
  ListChecks,
  Lock,
  MessageSquareText,
  Moon,
  Plus,
  Search,
  ShieldAlert,
  Sparkles,
  Sun,
  UploadCloud,
  UserRound,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

type ViewKey = "cases" | "plans" | "reviews" | "knowledge" | "history";
type Tone = "neutral" | "blue" | "green" | "amber" | "red" | "violet";
type Lang = "zh" | "en";
type Theme = "light" | "dark";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8010";

type ApiUser = { id: number; username: string; display_name: string; role: string; active: string };
type ApiCase = { id: number; case_key: string; title: string; module: string; case_type: string; priority: string; status: string; owner: string; steps?: string; expected_result?: string };
type ApiDocument = { id: number; filename: string; source_type: string; status: string; size: number; created_at: string };
type ApiAuditLog = { id: number; actor: string; action: string; entity_type: string; entity_id: string; summary: string; created_at: string };
type ApiPlan = { id: number; name: string; scope: string; owner: string; status: string; risk: string; release: string };
type ApiRun = { id: number; plan_id: number; name: string; cycle: string; assignee: string; status: string; passed: number; failed: number; blocked: number; total: number };
type ApiRunResult = { id: number; run_id: number; case_id: number; status: string; executor: string; actual_result: string; defect_url: string; executed_at: string | null };
type ApiReview = { id: number; title: string; submitter: string; reviewer: string; status: string; score: number; risk: string; case_count: number; summary: string };
type ApiComment = { id: number; entity_type: string; entity_id: string; author: string; body: string; created_at: string };
type ApiVersion = { id: number; case_id: number; version: number; actor: string; change_summary: string; snapshot: string; created_at: string };
type ApiIssue = { id: number; task_id: number; title: string; severity: string; status: string; recommendation: string; created_at: string };
type ApiImportJob = { id: number; filename: string; status: string; imported: number; updated: number; failed: number; created_by: string; created_at: string };

type CaseForm = { id?: number; case_key: string; title: string; module: string; case_type: string; priority: string; status: string; owner: string; steps: string; expected_result: string };

const emptyCaseForm: CaseForm = { case_key: "", title: "", module: "PSP Verification", case_type: "Functional", priority: "P1", status: "Draft", owner: "", steps: "", expected_result: "" };

const navIcons: Record<ViewKey, React.ComponentType<{ className?: string }>> = {
  cases: ListChecks,
  plans: ClipboardCheck,
  reviews: ShieldAlert,
  knowledge: FileStack,
  history: History,
};

const copy = {
  en: {
    app: "TestPilot AI",
    subtitle: "DPU QA workbench",
    tagline: "Test management + AI Copilot",
    nav: { cases: "Case Library", plans: "Plans & Runs", reviews: "Reviews", knowledge: "Knowledge", history: "Audit Log" },
    projectTree: "Project Tree",
    project: "Project",
    release: "Release",
    newCase: "New Case",
    language: "中文",
    dark: "Dark",
    light: "Light",
    caseLibrary: "Case Library",
    caseDesc: "CRUD, search, CSV import/export, comments, assignment, and version history.",
    template: "Template",
    import: "Import",
    export: "Export",
    new: "New",
    searchCases: "Search cases, modules, owners",
    caseDetail: "Case Detail / Comments / Versions",
    caseDetailDesc: "Every save creates a version snapshot; comments and assignments are audit tracked.",
    comment: "Comment",
    comments: "Comments",
    versions: "Versions",
    noComments: "No comments yet.",
    noVersions: "No version records.",
    importJobs: "Import Jobs",
    importJobsDesc: "Recent CSV imports include validation results.",
    editCase: "Edit Case",
    createCase: "New Case",
    formDesc: "Saved cases are written to FastAPI + SQLite and tracked in audit/version history.",
    save: "Save",
    cancel: "Cancel",
    plans: "Test Plans",
    plansDesc: "Release scope, risk, owners, and execution cycles.",
    runs: "Execution Cycles",
    runsDesc: "Run totals are recalculated from per-case results.",
    perCase: "Per-case Results",
    perCaseDesc: "Mark each case in the active run as Passed, Failed, or Blocked.",
    reviews: "Case Reviews",
    reviewsDesc: "Create review tasks from selected cases and move them through the review flow.",
    createReview: "Create Review",
    needsChanges: "Needs changes",
    approve: "Approve",
    knowledge: "Knowledge Base",
    knowledgeDesc: "Upload requirements, API specs, historical cases, and defect reviews for AI retrieval.",
    upload: "Upload",
    aiIssues: "AI Issues",
    aiIssuesDesc: "AI review findings can be persisted as follow-up items.",
    audit: "Audit Log",
    auditDesc: "All key workbench operations are traceable for a 20-person QA team.",
    login: "Login / Permissions",
    signIn: "Sign in",
    signOut: "Sign out",
    teamAdmin: "Team Admin",
    teamAdminDesc: "QA Lead can toggle roles for trial management.",
    toggle: "Toggle",
    aiCopilot: "AI Copilot",
    aiCopilotDesc: "Model workflow with persisted follow-up items.",
    generate: "Generate",
    reviewList: "Review List",
    saveAiDraft: "Save AI Draft Case",
    backendEmpty: "FastAPI responses will appear here.",
    citations: "Citations",
    noSources: "No uploaded sources yet.",
  },
  zh: {
    app: "TestPilot AI",
    subtitle: "DPU 测试工作台",
    tagline: "测试管理台 + AI Copilot",
    nav: { cases: "用例库", plans: "计划与执行", reviews: "用例评审", knowledge: "知识库", history: "审计日志" },
    projectTree: "项目结构",
    project: "项目",
    release: "版本",
    newCase: "新建用例",
    language: "English",
    dark: "夜间",
    light: "日间",
    caseLibrary: "用例库",
    caseDesc: "支持增删改查、搜索、CSV 导入导出、评论、指派和版本历史。",
    template: "模板",
    import: "导入",
    export: "导出",
    new: "新建",
    searchCases: "搜索用例、模块、负责人",
    caseDetail: "用例详情 / 评论 / 版本",
    caseDetailDesc: "每次保存都会生成版本快照，评论和指派会进入审计记录。",
    comment: "评论",
    comments: "评论",
    versions: "版本历史",
    noComments: "暂无评论。",
    noVersions: "暂无版本记录。",
    importJobs: "导入任务",
    importJobsDesc: "最近的 CSV 导入会显示校验结果。",
    editCase: "编辑用例",
    createCase: "新建用例",
    formDesc: "保存后写入 FastAPI + SQLite，并记录审计和版本快照。",
    save: "保存",
    cancel: "取消",
    plans: "测试计划",
    plansDesc: "管理版本范围、风险、负责人和执行轮次。",
    runs: "执行轮次",
    runsDesc: "执行统计会根据逐用例结果自动汇总。",
    perCase: "逐用例执行结果",
    perCaseDesc: "在当前轮次中标记每条用例为通过、失败或阻塞。",
    reviews: "用例评审",
    reviewsDesc: "从用例列表创建评审任务，并推进评审状态流。",
    createReview: "创建评审",
    needsChanges: "需修改",
    approve: "通过",
    knowledge: "知识库",
    knowledgeDesc: "上传需求、接口契约、历史用例和缺陷复盘，供 AI 检索引用。",
    upload: "上传",
    aiIssues: "AI 问题",
    aiIssuesDesc: "AI 评审发现的问题可以沉淀为跟进项。",
    audit: "审计日志",
    auditDesc: "关键操作都会记录，方便 20 人测试团队追踪责任和变更。",
    login: "登录 / 权限",
    signIn: "登录",
    signOut: "退出",
    teamAdmin: "团队管理",
    teamAdminDesc: "QA Lead 可在试用阶段切换成员角色。",
    toggle: "切换",
    aiCopilot: "AI Copilot",
    aiCopilotDesc: "模型工作流，并能保存跟进项。",
    generate: "生成",
    reviewList: "评审列表",
    saveAiDraft: "保存 AI 草稿用例",
    backendEmpty: "FastAPI 响应会显示在这里。",
    citations: "引用来源",
    noSources: "暂无已上传资料。",
  },
} as const;

const fallbackCases: ApiCase[] = [
  { id: 1, case_key: "TC-DPU-001", title: "New user completes registration and starts financing application", module: "Registration", case_type: "Functional", priority: "P0", status: "Ready", owner: "Maya" },
  { id: 2, case_key: "TC-DPU-014", title: "PSP verification succeeds after timeout retry", module: "PSP Verification", case_type: "Negative", priority: "P0", status: "Needs work", owner: "Alex" },
  { id: 3, case_key: "TC-DPU-022", title: "Shop information syncs after SP authorization", module: "SP Authorization", case_type: "Boundary", priority: "P1", status: "Draft", owner: "Nora" },
];

function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

function badgeTone(value: string): Tone {
  if (["P0", "High", "Failed"].includes(value)) return "red";
  if (["P1", "Medium", "Running", "Needs work", "Needs changes", "Draft", "Blocked", "Not Run"].includes(value)) return "amber";
  if (["Low", "Complete", "Approved", "Ready", "Passed", "Indexed", "Active"].includes(value)) return "green";
  if (["Functional", "Negative", "Boundary", "Regression", "review", "update", "create"].includes(value)) return "blue";
  return "neutral";
}

function authHeaders(token: string): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default function Home() {
  const [active, setActive] = useState<ViewKey>("cases");
  const [lang, setLang] = useState<Lang>("zh");
  const [theme, setTheme] = useState<Theme>("light");
  const [apiStatus, setApiStatus] = useState("Ready");
  const [apiResult, setApiResult] = useState("");
  const [token, setToken] = useState("");
  const [currentUser, setCurrentUser] = useState<ApiUser | null>(null);
  const [loginForm, setLoginForm] = useState({ username: "maya", password: "testpilot123" });
  const [users, setUsers] = useState<ApiUser[]>([]);
  const [cases, setCases] = useState<ApiCase[]>([]);
  const [documents, setDocuments] = useState<ApiDocument[]>([]);
  const [auditLogs, setAuditLogs] = useState<ApiAuditLog[]>([]);
  const [plans, setPlans] = useState<ApiPlan[]>([]);
  const [runs, setRuns] = useState<ApiRun[]>([]);
  const [runResults, setRunResults] = useState<ApiRunResult[]>([]);
  const [reviews, setReviews] = useState<ApiReview[]>([]);
  const [comments, setComments] = useState<ApiComment[]>([]);
  const [versions, setVersions] = useState<ApiVersion[]>([]);
  const [issues, setIssues] = useState<ApiIssue[]>([]);
  const [importJobs, setImportJobs] = useState<ApiImportJob[]>([]);
  const [query, setQuery] = useState("");
  const [caseForm, setCaseForm] = useState<CaseForm>(emptyCaseForm);
  const [showCaseForm, setShowCaseForm] = useState(false);
  const uploadRef = useRef<HTMLInputElement>(null);
  const importRef = useRef<HTMLInputElement>(null);
  const t = copy[lang];

  const visibleCases = cases.length ? cases : fallbackCases;
  const selectedCase = visibleCases[0];
  const selectedRun = runs[0];
  const filteredCases = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return visibleCases;
    return visibleCases.filter((item) => [item.case_key, item.title, item.module, item.priority, item.status, item.owner].join(" ").toLowerCase().includes(needle));
  }, [query, visibleCases]);

  async function apiFetch(path: string, options: RequestInit = {}) {
    const headers = new Headers(options.headers);
    if (token) headers.set("Authorization", `Bearer ${token}`);
    return fetch(`${API_BASE}${path}`, { ...options, headers });
  }

  async function refreshServerData(activeToken = token) {
    try {
      const headers = new Headers(authHeaders(activeToken));
      const [casesResponse, documentsResponse, auditResponse, plansResponse, runsResponse, reviewsResponse, usersResponse, issuesResponse, jobsResponse] = await Promise.all([
        fetch(`${API_BASE}/api/cases`),
        fetch(`${API_BASE}/api/documents`),
        fetch(`${API_BASE}/api/audit-logs`),
        fetch(`${API_BASE}/api/plans`, { headers }),
        fetch(`${API_BASE}/api/runs`, { headers }),
        fetch(`${API_BASE}/api/review-tasks`, { headers }),
        fetch(`${API_BASE}/api/users`, { headers }),
        fetch(`${API_BASE}/api/ai/issues`, { headers }),
        fetch(`${API_BASE}/api/import-jobs`, { headers }),
      ]);
      if (casesResponse.ok) setCases(await casesResponse.json());
      if (documentsResponse.ok) setDocuments(await documentsResponse.json());
      if (auditResponse.ok) setAuditLogs(await auditResponse.json());
      if (plansResponse.ok) setPlans(await plansResponse.json());
      if (runsResponse.ok) setRuns(await runsResponse.json());
      if (reviewsResponse.ok) setReviews(await reviewsResponse.json());
      if (usersResponse.ok) setUsers(await usersResponse.json());
      if (issuesResponse.ok) setIssues(await issuesResponse.json());
      if (jobsResponse.ok) setImportJobs(await jobsResponse.json());
      setApiStatus("Backend connected");
    } catch {
      setApiStatus("Backend offline; showing local sample data");
    }
  }

  async function loadCaseDetails(caseId: number) {
    try {
      const [commentResponse, versionResponse] = await Promise.all([
        apiFetch(`/api/comments?entity_type=test_case&entity_id=${caseId}`),
        apiFetch(`/api/cases/${caseId}/versions`),
      ]);
      if (commentResponse.ok) setComments(await commentResponse.json());
      if (versionResponse.ok) setVersions(await versionResponse.json());
    } catch {
      setComments([]);
      setVersions([]);
    }
  }

  async function loadRunResults(runId: number) {
    const response = await apiFetch(`/api/run-results?run_id=${runId}`);
    if (response.ok) setRunResults(await response.json());
  }

  useEffect(() => {
    const stored = localStorage.getItem("testpilot_token") ?? "";
    const storedUser = localStorage.getItem("testpilot_user");
    const storedLang = localStorage.getItem("testpilot_lang") as Lang | null;
    const storedTheme = localStorage.getItem("testpilot_theme") as Theme | null;
    if (stored) setToken(stored);
    if (storedUser) setCurrentUser(JSON.parse(storedUser));
    if (storedLang === "zh" || storedLang === "en") setLang(storedLang);
    if (storedTheme === "light" || storedTheme === "dark") setTheme(storedTheme);
    void refreshServerData(stored);
  }, []);

  function toggleLang() {
    const next = lang === "zh" ? "en" : "zh";
    setLang(next);
    localStorage.setItem("testpilot_lang", next);
  }

  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    localStorage.setItem("testpilot_theme", next);
  }

  useEffect(() => {
    if (selectedCase?.id) void loadCaseDetails(selectedCase.id);
  }, [selectedCase?.id, token]);

  useEffect(() => {
    if (selectedRun?.id) void loadRunResults(selectedRun.id);
  }, [selectedRun?.id, token]);

  async function login() {
    const response = await fetch(`${API_BASE}/api/auth/login`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(loginForm) });
    const json = await response.json();
    setApiResult(JSON.stringify(json, null, 2));
    if (response.ok) {
      setToken(json.token);
      setCurrentUser(json.user);
      localStorage.setItem("testpilot_token", json.token);
      localStorage.setItem("testpilot_user", JSON.stringify(json.user));
      setApiStatus(`Signed in as ${json.user.display_name}`);
      await refreshServerData(json.token);
    } else {
      setApiStatus("Login failed");
    }
  }

  function logout() {
    setToken("");
    setCurrentUser(null);
    localStorage.removeItem("testpilot_token");
    localStorage.removeItem("testpilot_user");
  }

  async function runGenerate() {
    const response = await apiFetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project: "DPU Financing",
        release: "DPU Regression v1.0",
        suite: "Financing Flow Regression",
        prompt: "Generate missing DPU regression cases for PSP timeout, retry, failure callback, SP authorization, and E-sign status.",
        output_type: "cases",
      }),
    });
    const json = await response.json();
    setApiStatus(response.ok ? "Generate complete" : "Generate failed");
    setApiResult(JSON.stringify(json, null, 2));
    await refreshServerData();
  }

  async function runReview() {
    const response = await apiFetch("/api/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project: "DPU Financing",
        release: "DPU Regression v1.0",
        suite: "Financing Flow Regression",
        content: visibleCases.map((row) => `${row.case_key} | ${row.title} | ${row.module} | ${row.status}`).join("\n"),
        criteria: ["requirement coverage", "negative scenarios", "observable expected results", "database assertions"],
      }),
    });
    const json = await response.json();
    setApiStatus(response.ok ? "Review complete" : "Review failed");
    setApiResult(JSON.stringify(json, null, 2));
    if (response.ok) {
      await createAiIssue(json.task_id ?? 1);
    }
    await refreshServerData();
  }

  async function createAiIssue(taskId: number) {
    const response = await apiFetch("/api/ai/issues", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task_id: taskId, title: "AI review follow-up: verify observable assertions", severity: "Medium", recommendation: "Add UI, webhook, and database assertions before approval." }),
    });
    if (response.ok) setIssues([await response.json(), ...issues]);
  }

  async function saveGeneratedDraftCase() {
    const key = `TC-DPU-AI-${Date.now().toString().slice(-5)}`;
    const response = await apiFetch("/api/ai/generated-cases/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        task_id: null,
        cases: [{ case_key: key, title: "AI generated draft case", module: "AI Coverage", case_type: "Functional", priority: "P1", status: "Draft", owner: currentUser?.display_name ?? "Maya", steps: "Review AI suggested coverage", expected_result: "Case is saved as draft", suite_id: null }],
      }),
    });
    setApiStatus(response.ok ? "Generated case saved" : "Save generated case failed");
    setApiResult(JSON.stringify(await response.json(), null, 2));
    await refreshServerData();
  }

  function startCreateCase() {
    setActive("cases");
    setCaseForm({ ...emptyCaseForm, case_key: `TC-DPU-${Date.now().toString().slice(-5)}`, owner: currentUser?.display_name ?? "" });
    setShowCaseForm(true);
  }

  function startEditCase(row: ApiCase) {
    setCaseForm({ id: row.id, case_key: row.case_key, title: row.title, module: row.module, case_type: row.case_type, priority: row.priority, status: row.status, owner: row.owner, steps: row.steps ?? "", expected_result: row.expected_result ?? "" });
    setShowCaseForm(true);
  }

  async function saveCase() {
    const endpoint = caseForm.id ? `/api/cases/${caseForm.id}` : "/api/cases";
    const response = await apiFetch(endpoint, { method: caseForm.id ? "PATCH" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(caseForm) });
    const json = await response.json();
    setApiStatus(response.ok ? "Case saved" : "Case save failed");
    setApiResult(JSON.stringify(json, null, 2));
    if (response.ok) {
      setShowCaseForm(false);
      setCaseForm(emptyCaseForm);
      await refreshServerData();
    }
  }

  async function deleteCase(row: ApiCase) {
    const response = await apiFetch(`/api/cases/${row.id}`, { method: "DELETE" });
    const json = await response.json();
    setApiStatus(response.ok ? "Case deleted" : "Case delete failed");
    setApiResult(JSON.stringify(json, null, 2));
    await refreshServerData();
  }

  async function addComment() {
    if (!selectedCase) return;
    const body = window.prompt(lang === "zh" ? "请输入评论" : "Comment");
    if (!body) return;
    const response = await apiFetch("/api/comments", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ entity_type: "test_case", entity_id: String(selectedCase.id), body }) });
    setApiStatus(response.ok ? "Comment added" : "Comment failed");
    setApiResult(JSON.stringify(await response.json(), null, 2));
    await loadCaseDetails(selectedCase.id);
    await refreshServerData();
  }

  async function exportCases() {
    const response = await apiFetch("/api/cases/export");
    const blob = await response.blob();
    const href = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = href;
    link.download = "test_cases.csv";
    link.click();
    URL.revokeObjectURL(href);
    setApiStatus(response.ok ? "CSV exported" : "CSV export failed");
    await refreshServerData();
  }

  async function downloadImportTemplate() {
    const response = await apiFetch("/api/cases/import-template");
    const blob = await response.blob();
    const href = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = href;
    link.download = "test_cases_import_template.csv";
    link.click();
    URL.revokeObjectURL(href);
  }

  async function importCases(file: File) {
    const form = new FormData();
    form.append("file", file);
    const response = await apiFetch("/api/cases/import", { method: "POST", body: form });
    setApiStatus(response.ok ? "CSV imported" : "CSV import failed");
    setApiResult(JSON.stringify(await response.json(), null, 2));
    await refreshServerData();
  }

  async function uploadDocument(file: File) {
    const form = new FormData();
    form.append("file", file);
    form.append("project", "DPU Financing");
    form.append("release", "DPU Regression v1.0");
    form.append("suite", "Financing Flow Regression");
    form.append("source_type", "Requirement");
    const response = await apiFetch("/api/documents/upload", { method: "POST", body: form });
    setApiStatus(response.ok ? "Upload queued" : "Upload failed");
    setApiResult(JSON.stringify(await response.json(), null, 2));
    await refreshServerData();
  }

  async function advanceReview(task: ApiReview, status: string) {
    const response = await apiFetch(`/api/review-tasks/${task.id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status, score: status === "Approved" ? Math.max(task.score, 90) : task.score }) });
    setApiStatus(response.ok ? `Review ${status}` : "Review update failed");
    setApiResult(JSON.stringify(await response.json(), null, 2));
    await refreshServerData();
  }

  async function createReviewTask() {
    const caseIds = visibleCases.slice(0, 3).map((item) => item.id);
    const response = await apiFetch("/api/review-tasks", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: `Review ${new Date().toLocaleTimeString()}`, submitter: currentUser?.display_name ?? "Maya", reviewer: "Nora", status: "Submitted", risk: "Medium", summary: "Review selected DPU cases", case_ids: caseIds }) });
    setApiStatus(response.ok ? "Review task created" : "Review task failed");
    setApiResult(JSON.stringify(await response.json(), null, 2));
    await refreshServerData();
  }

  async function updateRunResult(result: ApiRunResult, status: string) {
    const response = await apiFetch(`/api/run-results/${result.id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status, actual_result: `Marked ${status} from workbench` }) });
    setApiStatus(response.ok ? `Result ${status}` : "Result update failed");
    setApiResult(JSON.stringify(await response.json(), null, 2));
    if (selectedRun) await loadRunResults(selectedRun.id);
    await refreshServerData();
  }

  async function updateUserRole(user: ApiUser) {
    const nextRole = user.role === "QA Lead" ? "Functional QA" : "QA Lead";
    const response = await apiFetch(`/api/users/${user.id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ role: nextRole }) });
    setApiStatus(response.ok ? "User updated" : "User update failed");
    setApiResult(JSON.stringify(await response.json(), null, 2));
    await refreshServerData();
  }

  return (
    <main className={cx("min-h-screen text-slate-950", theme === "dark" ? "dark bg-slate-950 text-slate-100" : "bg-slate-100")}>
      <div className="flex min-h-screen">
        <aside className="hidden w-72 shrink-0 border-r border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950 lg:block">
          <div className="flex h-16 items-center gap-3 border-b border-slate-200 px-4 dark:border-slate-800">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-slate-950 text-white dark:bg-white dark:text-slate-950"><BrainCircuit className="h-5 w-5" /></div>
            <div><div className="text-sm font-semibold">{t.app}</div><div className="text-xs text-slate-500 dark:text-slate-400">{t.subtitle}</div></div>
          </div>
          <nav className="border-b border-slate-200 p-3 dark:border-slate-800">
            {(Object.keys(t.nav) as ViewKey[]).map((key) => {
              const Icon = navIcons[key];
              return <button key={key} onClick={() => setActive(key)} className={cx("flex h-9 w-full items-center gap-2 rounded-md px-3 text-sm font-medium", active === key ? "bg-slate-950 text-white dark:bg-white dark:text-slate-950" : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-900")}><Icon className="h-4 w-4" />{t.nav[key]}</button>;
            })}
          </nav>
          <ProjectTree labels={t} />
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="border-b border-slate-200 bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-950">
            <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
              <div><div className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">{t.tagline}</div><h1 className="mt-1 text-2xl font-semibold">{t.nav[active]}</h1></div>
              <div className="flex flex-wrap items-center gap-2">
                <ContextPill label={t.project} value="DPU Financing" />
                <ContextPill label={t.release} value="DPU Regression v1.0" />
                <Button variant="secondary" onClick={toggleLang}><Languages className="h-4 w-4" />{t.language}</Button>
                <Button variant="secondary" onClick={toggleTheme}>{theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}{theme === "dark" ? t.light : t.dark}</Button>
                <Button onClick={startCreateCase}><Plus className="h-4 w-4" />{t.newCase}</Button>
              </div>
            </div>
          </header>

          <div className="grid flex-1 gap-4 p-4 xl:grid-cols-[1fr_360px]">
            <div className="min-w-0 space-y-4">
              {active === "cases" && <CasesView labels={t} rows={filteredCases} selectedCase={selectedCase} showForm={showCaseForm} form={caseForm} setForm={setCaseForm} query={query} setQuery={setQuery} comments={comments} versions={versions} importJobs={importJobs} onCreate={startCreateCase} onEdit={startEditCase} onDelete={deleteCase} onSave={saveCase} onCancel={() => setShowCaseForm(false)} onAddComment={addComment} onExport={exportCases} onImportClick={() => importRef.current?.click()} onTemplate={downloadImportTemplate} />}
              {active === "plans" && <PlansView labels={t} plans={plans} runs={runs} runResults={runResults} onUpdateResult={updateRunResult} />}
              {active === "reviews" && <ReviewsView labels={t} reviews={reviews} onAdvance={advanceReview} onCreate={createReviewTask} />}
              {active === "knowledge" && <KnowledgeView labels={t} documents={documents} issues={issues} onUploadClick={() => uploadRef.current?.click()} />}
              {active === "history" && <HistoryView labels={t} logs={auditLogs} />}
            </div>
            <Copilot labels={t} user={currentUser} users={users} loginForm={loginForm} setLoginForm={setLoginForm} onLogin={login} onLogout={logout} onUpdateUser={updateUserRole} apiStatus={apiStatus} apiResult={apiResult} onGenerate={runGenerate} onReview={runReview} onSaveGenerated={saveGeneratedDraftCase} documents={documents} />
          </div>
        </div>
      </div>
      <input ref={uploadRef} type="file" className="hidden" onChange={(event) => { const file = event.target.files?.[0]; if (file) void uploadDocument(file); event.currentTarget.value = ""; }} />
      <input ref={importRef} type="file" accept=".csv,text/csv" className="hidden" onChange={(event) => { const file = event.target.files?.[0]; if (file) void importCases(file); event.currentTarget.value = ""; }} />
    </main>
  );
}

function Button({ children, variant = "primary", onClick, className }: { children: React.ReactNode; variant?: "primary" | "secondary" | "ghost"; onClick?: () => void; className?: string }) {
  return <button onClick={onClick} className={cx("inline-flex h-9 items-center justify-center gap-2 rounded-md px-3 text-sm font-medium transition", variant === "primary" && "bg-slate-950 text-white hover:bg-slate-800 dark:bg-white dark:text-slate-950 dark:hover:bg-slate-200", variant === "secondary" && "border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200 dark:hover:bg-slate-900", variant === "ghost" && "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-900", className)}>{children}</button>;
}

function Badge({ children, tone = "neutral" }: { children: React.ReactNode; tone?: Tone }) {
  return <span className={cx("inline-flex h-6 items-center rounded-md border px-2 text-xs font-medium", tone === "neutral" && "border-slate-200 bg-white text-slate-600 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-300", tone === "blue" && "border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-900 dark:bg-blue-950 dark:text-blue-200", tone === "green" && "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-200", tone === "amber" && "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200", tone === "red" && "border-red-200 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-200", tone === "violet" && "border-violet-200 bg-violet-50 text-violet-700 dark:border-violet-900 dark:bg-violet-950 dark:text-violet-200")}>{children}</span>;
}

function Surface({ children, className }: { children: React.ReactNode; className?: string }) {
  return <section className={cx("rounded-lg border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950", className)}>{children}</section>;
}

function SectionHeader({ title, desc, action }: { title: string; desc?: string; action?: React.ReactNode }) {
  return <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-4 py-3 dark:border-slate-800"><div><h2 className="text-base font-semibold text-slate-950 dark:text-slate-50">{title}</h2>{desc ? <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{desc}</p> : null}</div>{action}</div>;
}

function ContextPill({ label, value }: { label: string; value: string }) {
  return <div className="inline-flex h-9 items-center gap-2 rounded-md border border-slate-200 bg-white px-3 text-sm dark:border-slate-700 dark:bg-slate-950"><span className="text-slate-500 dark:text-slate-400">{label}</span><span className="font-medium">{value}</span></div>;
}

function ProjectTree({ labels }: { labels: typeof copy[Lang] }) {
  const groups = [["Financing Flow", "42", ["Registration", "SP Authorization", "PSP Verification", "E-sign"]], ["Merchant Account", "28", ["User Registration", "Account Status", "Merchant Profile"]], ["Post-loan Flow", "19", ["Drawdown", "Repayment", "Status Callback"]]];
  return <div className="p-3"><div className="mb-3 flex items-center gap-2 px-2 text-sm font-semibold"><FolderTree className="h-4 w-4" />{labels.projectTree}</div><div className="space-y-3">{groups.map(([group, count, children]) => <div key={group as string}><div className="flex h-8 items-center justify-between rounded-md px-2 text-sm font-medium text-slate-800 dark:text-slate-100"><span>{group}</span><Badge>{count}</Badge></div><div className="mt-1 space-y-1 border-l border-slate-200 pl-3 dark:border-slate-800">{(children as string[]).map((child) => <div key={child} className="h-7 rounded px-2 text-sm text-slate-500 dark:text-slate-400">{child}</div>)}</div></div>)}</div></div>;
}

function CasesView({ labels, rows, selectedCase, showForm, form, setForm, query, setQuery, comments, versions, importJobs, onCreate, onEdit, onDelete, onSave, onCancel, onAddComment, onExport, onImportClick, onTemplate }: { labels: typeof copy[Lang]; rows: ApiCase[]; selectedCase?: ApiCase; showForm: boolean; form: CaseForm; setForm: (form: CaseForm) => void; query: string; setQuery: (value: string) => void; comments: ApiComment[]; versions: ApiVersion[]; importJobs: ApiImportJob[]; onCreate: () => void; onEdit: (row: ApiCase) => void; onDelete: (row: ApiCase) => void; onSave: () => void; onCancel: () => void; onAddComment: () => void; onExport: () => void; onImportClick: () => void; onTemplate: () => void }) {
  return <div className="space-y-4">{showForm && <CaseFormPanel labels={labels} form={form} setForm={setForm} onSave={onSave} onCancel={onCancel} />}<Surface><SectionHeader title={labels.caseLibrary} desc={labels.caseDesc} action={<div className="flex flex-wrap gap-2"><Button variant="secondary" onClick={onTemplate}><Download className="h-4 w-4" />{labels.template}</Button><Button variant="secondary" onClick={onImportClick}><UploadCloud className="h-4 w-4" />{labels.import}</Button><Button variant="secondary" onClick={onExport}><Download className="h-4 w-4" />{labels.export}</Button><Button onClick={onCreate}><Plus className="h-4 w-4" />{labels.new}</Button></div>} /><div className="flex flex-wrap gap-2 border-b border-slate-200 p-4 dark:border-slate-800"><label className="relative min-w-72 flex-1"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" /><input className="h-9 w-full rounded-md border border-slate-200 bg-white pl-9 pr-3 text-sm outline-none focus:border-slate-400 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100" placeholder={labels.searchCases} value={query} onChange={(event) => setQuery(event.target.value)} /></label></div><DataTable headers={["ID", "Title", "Module", "Type", "Priority", "Status", "Owner", "Actions"]} rows={rows.map((row) => [row.case_key, row.title, row.module, row.case_type, row.priority, row.status, row.owner, row.id])} renderActions={(row) => { const target = rows.find((item) => item.id === row[7]); if (!target) return null; return <div className="flex gap-2"><Button variant="secondary" onClick={() => onEdit(target)}>Edit</Button><Button variant="ghost" onClick={() => onDelete(target)}>Delete</Button></div>; }} /></Surface><Surface><SectionHeader title={labels.caseDetail} desc={labels.caseDetailDesc} action={<Button variant="secondary" onClick={onAddComment}><MessageSquareText className="h-4 w-4" />{labels.comment}</Button>} /><div className="grid gap-4 p-4 lg:grid-cols-3"><div className="rounded-md border border-slate-200 bg-slate-50 p-4 text-sm dark:border-slate-800 dark:bg-slate-900"><InfoRow label="ID" value={selectedCase?.case_key ?? "-"} /><InfoRow label="Module" value={selectedCase?.module ?? "-"} /><InfoRow label="Status" value={selectedCase?.status ?? "-"} /><InfoRow label="Owner" value={selectedCase?.owner ?? "-"} /></div><div className="space-y-3"><div className="text-sm font-semibold">{labels.comments}</div>{comments.length ? comments.slice(0, 4).map((comment) => <div key={comment.id} className="rounded-md border border-slate-200 p-3 text-sm dark:border-slate-800"><div className="font-medium">{comment.author}</div><p className="mt-1 text-slate-600 dark:text-slate-300">{comment.body}</p></div>) : <p className="text-sm text-slate-500 dark:text-slate-400">{labels.noComments}</p>}</div><div className="space-y-3"><div className="text-sm font-semibold">{labels.versions}</div>{versions.length ? versions.slice(0, 4).map((version) => <div key={version.id} className="rounded-md border border-slate-200 p-3 text-sm dark:border-slate-800"><div className="flex items-center justify-between"><span>v{version.version}</span><span className="text-slate-500 dark:text-slate-400">{version.actor}</span></div><p className="mt-1 text-slate-600 dark:text-slate-300">{version.change_summary}</p></div>) : <p className="text-sm text-slate-500 dark:text-slate-400">{labels.noVersions}</p>}</div></div></Surface><Surface><SectionHeader title={labels.importJobs} desc={labels.importJobsDesc} /><DataTable headers={["File", "Status", "Imported", "Updated", "Failed", "By"]} rows={importJobs.slice(0, 5).map((job) => [job.filename, job.status, job.imported, job.updated, job.failed, job.created_by])} /></Surface></div>;
}

function CaseFormPanel({ labels, form, setForm, onSave, onCancel }: { labels: typeof copy[Lang]; form: CaseForm; setForm: (form: CaseForm) => void; onSave: () => void; onCancel: () => void }) {
  const update = (key: keyof CaseForm, value: string) => setForm({ ...form, [key]: value });
  return <Surface><SectionHeader title={form.id ? labels.editCase : labels.createCase} desc={labels.formDesc} action={<div className="flex gap-2"><Button variant="secondary" onClick={onCancel}>{labels.cancel}</Button><Button onClick={onSave}>{labels.save}</Button></div>} /><div className="grid gap-3 p-4 md:grid-cols-2 xl:grid-cols-4"><Field label="ID" value={form.case_key} onChange={(value) => update("case_key", value)} disabled={Boolean(form.id)} /><Field label="Module" value={form.module} onChange={(value) => update("module", value)} /><Field label="Type" value={form.case_type} onChange={(value) => update("case_type", value)} /><Field label="Priority" value={form.priority} onChange={(value) => update("priority", value)} /><Field label="Status" value={form.status} onChange={(value) => update("status", value)} /><Field label="Owner" value={form.owner} onChange={(value) => update("owner", value)} /><label className="md:col-span-2"><span className="text-sm font-medium text-slate-700 dark:text-slate-300">Title</span><input className="mt-2 h-9 w-full rounded-md border border-slate-200 px-3 text-sm outline-none focus:border-slate-400 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100" value={form.title} onChange={(event) => update("title", event.target.value)} /></label><label className="md:col-span-2"><span className="text-sm font-medium text-slate-700 dark:text-slate-300">Steps</span><textarea className="mt-2 h-24 w-full rounded-md border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-400 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100" value={form.steps} onChange={(event) => update("steps", event.target.value)} /></label><label className="md:col-span-2"><span className="text-sm font-medium text-slate-700 dark:text-slate-300">Expected Result</span><textarea className="mt-2 h-24 w-full rounded-md border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-400 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100" value={form.expected_result} onChange={(event) => update("expected_result", event.target.value)} /></label></div></Surface>;
}

function PlansView({ labels, plans, runs, runResults, onUpdateResult }: { labels: typeof copy[Lang]; plans: ApiPlan[]; runs: ApiRun[]; runResults: ApiRunResult[]; onUpdateResult: (result: ApiRunResult, status: string) => void }) {
  return <div className="space-y-4"><Surface><SectionHeader title={labels.plans} desc={labels.plansDesc} /><DataTable headers={["Plan", "Scope", "Risk", "Owner", "Status", "Release"]} rows={plans.map((plan) => [plan.name, plan.scope, plan.risk, plan.owner, plan.status, plan.release])} /></Surface><Surface><SectionHeader title={labels.runs} desc={labels.runsDesc} /><DataTable headers={["Run", "Cycle", "Assignee", "Status", "Passed", "Failed", "Blocked", "Total"]} rows={runs.map((run) => [run.name, run.cycle, run.assignee, run.status, run.passed, run.failed, run.blocked, run.total])} /></Surface><Surface><SectionHeader title={labels.perCase} desc={labels.perCaseDesc} /><DataTable headers={["Result ID", "Case ID", "Status", "Executor", "Actual", "Defect", "Actions"]} rows={runResults.map((result) => [result.id, result.case_id, result.status, result.executor, result.actual_result || "-", result.defect_url || "-", result.id])} renderActions={(row) => { const target = runResults.find((item) => item.id === row[6]); if (!target) return null; return <div className="flex gap-2"><Button variant="secondary" onClick={() => onUpdateResult(target, "Passed")}>Pass</Button><Button variant="secondary" onClick={() => onUpdateResult(target, "Failed")}>Fail</Button><Button variant="ghost" onClick={() => onUpdateResult(target, "Blocked")}>Block</Button></div>; }} /></Surface></div>;
}

function ReviewsView({ labels, reviews, onAdvance, onCreate }: { labels: typeof copy[Lang]; reviews: ApiReview[]; onAdvance: (task: ApiReview, status: string) => void; onCreate: () => void }) {
  return <Surface><SectionHeader title={labels.reviews} desc={labels.reviewsDesc} action={<Button onClick={onCreate}><Plus className="h-4 w-4" />{labels.createReview}</Button>} /><DataTable headers={["Task", "Submitter", "Reviewer", "Cases", "Score", "Risk", "Status", "Actions"]} rows={reviews.map((task) => [task.title, task.submitter, task.reviewer, task.case_count, task.score, task.risk, task.status, task.id])} renderActions={(row) => { const target = reviews.find((item) => item.id === row[7]); if (!target) return null; return <div className="flex gap-2"><Button variant="secondary" onClick={() => onAdvance(target, "Needs changes")}>{labels.needsChanges}</Button><Button onClick={() => onAdvance(target, "Approved")}>{labels.approve}</Button></div>; }} /></Surface>;
}

function KnowledgeView({ labels, documents, issues, onUploadClick }: { labels: typeof copy[Lang]; documents: ApiDocument[]; issues: ApiIssue[]; onUploadClick: () => void }) {
  return <div className="space-y-4"><Surface><SectionHeader title={labels.knowledge} desc={labels.knowledgeDesc} action={<Button onClick={onUploadClick}><UploadCloud className="h-4 w-4" />{labels.upload}</Button>} /><DataTable headers={["Source", "Type", "Index Status", "Size", "Updated"]} rows={documents.map((item) => [item.filename, item.source_type, item.status, item.size, new Date(item.created_at).toLocaleString()])} /></Surface><Surface><SectionHeader title={labels.aiIssues} desc={labels.aiIssuesDesc} /><DataTable headers={["Title", "Severity", "Status", "Recommendation", "Created"]} rows={issues.map((issue) => [issue.title, issue.severity, issue.status, issue.recommendation, new Date(issue.created_at).toLocaleString()])} /></Surface></div>;
}

function HistoryView({ labels, logs }: { labels: typeof copy[Lang]; logs: ApiAuditLog[] }) {
  return <Surface><SectionHeader title={labels.audit} desc={labels.auditDesc} /><DataTable headers={["Activity", "Type", "Actor", "Entity", "Time"]} rows={logs.map((log) => [log.summary, log.action, log.actor, log.entity_type, new Date(log.created_at).toLocaleString()])} /></Surface>;
}

function DataTable({ headers, rows, renderActions }: { headers: readonly string[]; rows: readonly (readonly (string | number)[])[]; renderActions?: (row: readonly (string | number)[]) => React.ReactNode }) {
  return <div className="overflow-x-auto"><table className="w-full min-w-[860px] text-left text-sm"><thead className="bg-slate-50 text-xs font-semibold uppercase text-slate-500 dark:bg-slate-900 dark:text-slate-400"><tr>{headers.map((head) => <th key={head} className="px-4 py-3">{head}</th>)}</tr></thead><tbody className="divide-y divide-slate-200 dark:divide-slate-800">{rows.map((row, rowIndex) => <tr key={`${row.join("-")}-${rowIndex}`} className="hover:bg-slate-50 dark:hover:bg-slate-900">{row.slice(0, renderActions ? -1 : undefined).map((cell, index) => <td key={`${cell}-${index}`} className={cx("px-4 py-3", index === 0 || index === 1 ? "font-medium text-slate-950 dark:text-slate-50" : "text-slate-600 dark:text-slate-300")}>{renderCell(String(cell))}</td>)}{renderActions ? <td className="px-4 py-3">{renderActions(row)}</td> : null}</tr>)}</tbody></table></div>;
}

function renderCell(cell: string) {
  const tone = badgeTone(cell);
  return tone === "neutral" ? cell : <Badge tone={tone}>{cell}</Badge>;
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return <div className="mb-3 flex items-center justify-between gap-4"><span className="text-slate-500 dark:text-slate-400">{label}</span><span className="font-medium text-slate-950 dark:text-slate-50">{renderCell(value)}</span></div>;
}

function Field({ label, value, onChange, disabled = false }: { label: string; value: string; onChange: (value: string) => void; disabled?: boolean }) {
  return <label><span className="text-sm font-medium text-slate-700 dark:text-slate-300">{label}</span><input disabled={disabled} className="mt-2 h-9 w-full rounded-md border border-slate-200 px-3 text-sm outline-none focus:border-slate-400 disabled:bg-slate-100 disabled:text-slate-500 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100 dark:disabled:bg-slate-900" value={value} onChange={(event) => onChange(event.target.value)} /></label>;
}

function Copilot({ labels, user, users, loginForm, setLoginForm, onLogin, onLogout, onUpdateUser, apiStatus, apiResult, onGenerate, onReview, onSaveGenerated, documents }: { labels: typeof copy[Lang]; user: ApiUser | null; users: ApiUser[]; loginForm: { username: string; password: string }; setLoginForm: (value: { username: string; password: string }) => void; onLogin: () => void; onLogout: () => void; onUpdateUser: (user: ApiUser) => void; apiStatus: string; apiResult: string; onGenerate: () => void; onReview: () => void; onSaveGenerated: () => void; documents: ApiDocument[] }) {
  return <aside className="space-y-4"><Surface><SectionHeader title={labels.login} desc={user ? `${user.display_name} - ${user.role}` : "Default: maya / testpilot123"} action={user ? <Badge tone="green">Active</Badge> : <Badge tone="amber">Required</Badge>} /><div className="space-y-3 p-4">{user ? <div className="flex items-center justify-between rounded-md border border-slate-200 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-900"><div className="flex items-center gap-2 text-sm"><UserRound className="h-4 w-4" />{user.display_name}</div><Button variant="secondary" onClick={onLogout}>{labels.signOut}</Button></div> : <><Field label="Username" value={loginForm.username} onChange={(username) => setLoginForm({ ...loginForm, username })} /><Field label="Password" value={loginForm.password} onChange={(password) => setLoginForm({ ...loginForm, password })} /><Button className="w-full" onClick={onLogin}><Lock className="h-4 w-4" />{labels.signIn}</Button></>}</div></Surface><Surface><SectionHeader title={labels.teamAdmin} desc={labels.teamAdminDesc} /><div className="space-y-2 p-4">{users.slice(0, 5).map((item) => <div key={item.id} className="flex items-center justify-between rounded-md border border-slate-200 p-2 text-sm dark:border-slate-800"><div><div className="font-medium">{item.display_name}</div><div className="text-slate-500 dark:text-slate-400">{item.role}</div></div><Button variant="secondary" onClick={() => onUpdateUser(item)}>{labels.toggle}</Button></div>)}</div></Surface><Surface><SectionHeader title={labels.aiCopilot} desc={labels.aiCopilotDesc} action={<Badge tone="violet">gpt-5.4-mini</Badge>} /><div className="space-y-3 p-4"><Button className="w-full" onClick={onGenerate}><Sparkles className="h-4 w-4" />{labels.generate}</Button><Button variant="secondary" className="w-full justify-start" onClick={onReview}><MessageSquareText className="h-4 w-4" />{labels.reviewList}</Button><Button variant="secondary" className="w-full justify-start" onClick={onSaveGenerated}><Bot className="h-4 w-4" />{labels.saveAiDraft}</Button></div></Surface><Surface><SectionHeader title="Backend" desc={apiStatus} /><pre className="max-h-72 overflow-auto whitespace-pre-wrap p-4 text-xs leading-5 text-slate-600 dark:text-slate-300">{apiResult || labels.backendEmpty}</pre></Surface><Surface><SectionHeader title={labels.citations} /><div className="space-y-3 p-4">{documents.slice(0, 3).map((source) => <div key={source.id} className="rounded-md border border-slate-200 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-900"><div className="flex items-center gap-2 text-sm font-medium"><FileText className="h-4 w-4 text-slate-500" />{source.filename}</div><div className="mt-2"><Badge tone="blue">{source.source_type}</Badge></div></div>)}{!documents.length ? <p className="text-sm text-slate-500 dark:text-slate-400">{labels.noSources}</p> : null}</div></Surface></aside>;
}
