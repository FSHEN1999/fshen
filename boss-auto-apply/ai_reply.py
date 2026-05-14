"""
AI 辅助回复 - 用 Hermes CLI 作为 LLM backend（免费、本地、已配置）

设计原则：
1. 只有高价值意图才走 AI：ask_tech_detail, ask_project, ask_salary, greeting, match_review
2. 超时 20s / 失败 / 空输出 → 返回 None，调用方 fallback 到规则引擎
3. 单次 prompt 自包含：JD + 薪资 + 对话历史 + 简历高亮 + 意图指令
4. 429 限流短退避重试；其他失败/空输出仍快速 fallback 到规则引擎
"""
import subprocess
import shutil
import os
import json
import time
import urllib.request
import urllib.error
from typing import Optional
from candidate_profile import resume_brief, load_resume

try:
    from local_rag import retrieve_context
except Exception:
    def retrieve_context(*_args, **_kwargs):
        return ""


def _load_local_ps_env() -> None:
    """Load simple $env:NAME = "value" entries from ignored local env files."""
    env_path = os.path.join(os.path.dirname(__file__), ".env.local.ps1")
    if not os.path.exists(env_path):
        return
    try:
        import re
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                match = re.match(r'^\s*\$env:([A-Za-z_][A-Za-z0-9_]*)\s*=\s*["\'](.*)["\']\s*$', line)
                if match and not os.environ.get(match.group(1)):
                    os.environ[match.group(1)] = match.group(2)
    except Exception:
        return


_load_local_ps_env()

# === Hermes CLI 位置 ===
HERMES_BIN = shutil.which("hermes") or "/root/.hermes/hermes-agent/venv/bin/hermes"
# Windows 下通过 wsl.exe 转发调用 Hermes（BOSS 跑 Windows Python，hermes 在 WSL 内）
IS_WINDOWS = os.name == "nt"
WSL_EXE = r"C:\Windows\System32\wsl.exe"
HERMES_WSL_PATH = "/root/.hermes/hermes-agent/venv/bin/hermes"

# === 开关：环境变量 BOSS_AI_REPLY=1 启用，默认关闭保守 ===
AI_ENABLED = os.environ.get("BOSS_AI_REPLY", "0") == "1"
AI_PROVIDER = os.environ.get("BOSS_AI_PROVIDER", "hermes").strip().lower()
QWEN_BASE_URL = os.environ.get("BOSS_QWEN_BASE_URL", "").strip().rstrip("/")
QWEN_API_KEY = os.environ.get("BOSS_QWEN_API_KEY", "").strip()
QWEN_MODEL = os.environ.get("BOSS_QWEN_MODEL", "qwen3.6-plus").strip()
AI_LOG_FILE = os.path.join(os.path.dirname(__file__), "data", "ai_calls.jsonl")
QWEN_MAX_RETRIES = int(os.environ.get("BOSS_QWEN_MAX_RETRIES", "2") or "2")
QWEN_RETRY_BASE_DELAY = float(os.environ.get("BOSS_QWEN_RETRY_BASE_DELAY", "1") or "1")
QWEN_RETRY_MAX_DELAY = float(os.environ.get("BOSS_QWEN_RETRY_MAX_DELAY", "12") or "12")
HERMES_MAX_RETRIES = int(os.environ.get("BOSS_HERMES_MAX_RETRIES", "2") or "2")
HERMES_RETRY_BASE_DELAY = float(os.environ.get("BOSS_HERMES_RETRY_BASE_DELAY", "1") or "1")
HERMES_RETRY_MAX_DELAY = float(os.environ.get("BOSS_HERMES_RETRY_MAX_DELAY", "12") or "12")

# === 哪些意图值得走 AI ===
AI_INTENTS = {
    "greeting",
    "match_review",
    "unknown",
    "ask_salary",
    "ask_experience",
    "ask_skills",
    "ask_education",
    "ask_available",
    "interview_invite",
    "ask_resume",
    "ask_location",
    "ask_project",
    "ask_age",
    "ask_contact",
    "ask_tech_detail",
    "ask_outsource",
    "ask_overtime",
    "hr_ask_status",
}

# === 简历高亮：由 .env.local.ps1 / 环境变量注入，等待用户简历后填充 ===
RESUME_BRIEF = resume_brief()


def should_use_ai(intent: str) -> bool:
    """判断该意图是否应走 AI"""
    return AI_ENABLED and intent in AI_INTENTS


def _log_ai_event(event: dict) -> None:
    """Write AI call telemetry without prompts or secrets."""
    try:
        os.makedirs(os.path.dirname(AI_LOG_FILE), exist_ok=True)
        payload = {
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            **event,
        }
        with open(AI_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        return


def _retry_after_seconds(headers, fallback: float, max_delay: float) -> float:
    try:
        raw = headers.get("Retry-After") if headers else None
        if raw:
            return min(float(raw), max_delay)
    except Exception:
        pass
    return min(float(fallback), max_delay)


def _looks_rate_limited(text: str) -> bool:
    lowered = (text or "").lower()
    return "429" in lowered or "rate limit" in lowered or "too many requests" in lowered


def build_prompt(intent: str, messages: list, job_info: dict) -> str:
    """构造自包含 prompt"""
    # 对话历史（最近 6 条）
    history = ""
    if messages:
        recent = messages[-6:]
        for m in recent:
            role = "HR" if m.get("role") == "hr" else "我"
            history += f"{role}: {m.get('text','').strip()}\n"

    # 职位信息摘要
    job_desc = f"职位：{job_info.get('title','未知')} / 公司：{job_info.get('company','未知')} / 薪资：{job_info.get('salary','未知')}\n"
    if job_info.get("jd"):
        job_desc += f"JD正文（节选）：{job_info['jd'][:600]}\n"
    if job_info.get("tags"):
        job_desc += f"标签：{', '.join(job_info['tags'])}\n"

    rag_context = retrieve_context(intent, messages or [], job_info or {})

    intent_hint = {
        "ask_tech_detail": "HR问技术细节。像真人聊天一样答，只抓1个最相关场景，1-2句，别堆术语，别像简历。",
        "ask_project": "HR问项目经验。只挑1个最贴岗位的项目，1-2句讲清你做了什么、结果怎样，不要罗列职责。",
        "ask_salary": "HR问期望薪资/在职状态。参考JD薪资：若岗位匹配度高可答18-30K；偏低就说'可以谈，先聊聊工作内容'。目前在职，合适可尽快推进。<=2句。",
        "greeting": (
            "开场白。要求：\n"
            "  ① 从JD正文里挑1-2个原文出现的测试词或业务场景(如测试计划/自动化/回归/上线验证/数据迁移)，证明看了JD\n"
            "  ② 1句话点出我简历里最匹配的经验(银行测试/接口自动化/数据库一致性/测试负责人 任挑最贴的)\n"
            "  ③ 结尾自然引向细聊(方便聊下具体业务吗)\n"
            "  ④ 总长度60-120字，不要'您好HR您好'叠词，不要尬吹公司\n"
            "  ⑤ 每个职位招呼语必须不同——绝不套模板\n"
            "示例：您好，看JD里提到测试计划和上线验证，我之前做过银行/跨境金融平台的测试负责人，负责接口自动化和数据库一致性校验，方便聊下贵司这边的测试覆盖重点吗？"
        ),
        "unknown": "HR消息意图不明。顺着最后一句自然接话，1句就够，别写成长段。",
        "interview_invite": (
            "HR发面试邀请。规则：\n"
            "  ① HR已给具体时间(如周一上午11点)→直接确认'好的，{时间}没问题，地址/会议链接发我'\n"
            "  ② HR已给地址/链接→不要再问\n"
            "  ③ 时间未定→说工作日时间灵活，请HR定\n"
            "  ④ 还没交换联系方式→结尾加一句'方便加个微信，当天好联系'\n"
            "  ⑤ <=3句，专业利落"
        ),
        "ask_resume": "HR要简历。只回'好，简历发您。' 不要额外带微信、电话、联系方式。",
        "ask_identity_info": "HR要身份证号/证件信息。不要提供证件号，不要给身份证照片。明确说明这类敏感信息只会在确认公司主体和正式流程后，通过官方系统或线下面试安全提供。<=2句。",
        "ask_outsource": "HR问能否接受外包/驻场。看JD性质：银行/金融驻场→'可以，做过银行项目测试'；普通外包→'可以考虑，主要看项目范围'。<=2句，别反问。",
        "hr_ask_status": "HR问当前状态/在看吗/方便聊吗。像聊天一样回，1句到2句，别写成长段。",
        "ask_experience": "HR问年限/经历。先说年限，再补1个最相关项目点，最多2句。",
        "ask_skills": "HR问技术栈。只说最贴岗位的3-4个点，1句到2句，别像技能清单。",
        "ask_education": "HR问学历。直接答本科，学信网可查；如果问证书，简洁配合，<=1句。",
        "ask_available": "HR问是否在看/是否方便/到岗时间。答在职看机会，合适可推进，通常可在合适时间安排到岗，<=2句。",
        "ask_location": "HR问地点/通勤/是否在深圳。直接正常说人在深圳，线下面试可以，1句到2句。",
        "ask_age": "HR问年龄。直接答年龄信息，不展开隐私，<=1句。",
        "ask_contact": "HR要联系方式。不要输出任何微信号、手机号、占位符，留空让上游人工接管。",
        "ask_overtime": "HR问加班/节奏。正常口语回答，最多2句，别太书面。",
    }.get(intent, "根据HR最近的问题给出专业简洁回复，<=3句。")

    candidate_name = load_resume().get("name", "候选人")
    prompt = f"""你是求职者{candidate_name}在 BOSS 直聘上用的 AI 回复助手。输出将被直接发给 HR。

【我的简历】
{RESUME_BRIEF}

【RAG补充资料】
{rag_context or "无"}

【本次岗位】
{job_desc}
【对话历史】
{history}
【本次任务】
{intent_hint}

输出要求：
- 只输出要发给HR的正文，不要任何前后缀/解释/引号/markdown
- 口语但专业，不要啰嗦，不要用"您好！"开头（除非是greeting意图）
- 不要反问"方便聊聊吗"类废话，结论先行
- 中文
- 最多3句话
"""
    return prompt


def call_hermes(prompt: str, timeout: int = 60, purpose: str = "reply") -> Optional[str]:
    """调用 Hermes CLI：hermes chat -q <prompt> -Q -t "" 单轮非交互
    Windows 下通过 wsl.exe 转发到 WSL 里的 hermes 二进制。
    """
    start = time.time()
    print(f"  AI调用开始 provider=hermes purpose={purpose} prompt_chars={len(prompt)}", flush=True)
    # 选择执行命令
    if IS_WINDOWS:
        if not os.path.exists(WSL_EXE):
            _log_ai_event({
                "provider": "hermes",
                "purpose": purpose,
                "status": "missing_wsl",
                "prompt_chars": len(prompt),
            })
            return None
        cmd = [WSL_EXE, "--", HERMES_WSL_PATH, "chat", "-q", prompt, "-Q", "-t", ""]
    else:
        if not HERMES_BIN or not os.path.exists(HERMES_BIN):
            _log_ai_event({
                "provider": "hermes",
                "purpose": purpose,
                "status": "missing_binary",
                "prompt_chars": len(prompt),
            })
            return None
        cmd = [HERMES_BIN, "chat", "-q", prompt, "-Q", "-t", ""]
    for attempt in range(HERMES_MAX_RETRIES + 1):
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="ignore",
            )
            combined_error = f"{result.stdout or ''}\n{result.stderr or ''}"
            if result.returncode != 0 and _looks_rate_limited(combined_error) and attempt < HERMES_MAX_RETRIES:
                delay = min(HERMES_RETRY_BASE_DELAY * (2 ** attempt), HERMES_RETRY_MAX_DELAY)
                print(f"  Hermes 触发限流，{delay:.1f}s 后重试 ({attempt + 1}/{HERMES_MAX_RETRIES})", flush=True)
                time.sleep(delay)
                continue
            break
        except subprocess.TimeoutExpired:
            elapsed = int((time.time() - start) * 1000)
            print(f"  AI 回复超时 provider=hermes purpose={purpose} elapsed_ms={elapsed}，fallback 规则引擎", flush=True)
            _log_ai_event({
                "provider": "hermes",
                "purpose": purpose,
                "status": "timeout",
                "elapsed_ms": elapsed,
                "prompt_chars": len(prompt),
            })
            return None
        except Exception as e:
            elapsed = int((time.time() - start) * 1000)
            print(f"  AI 回复异常 provider=hermes purpose={purpose} elapsed_ms={elapsed}: {e}，fallback 规则引擎", flush=True)
            _log_ai_event({
                "provider": "hermes",
                "purpose": purpose,
                "status": "exception",
                "elapsed_ms": elapsed,
                "prompt_chars": len(prompt),
                "error": str(e)[:180],
            })
            return None

    try:
        if result.returncode != 0:
            elapsed = int((time.time() - start) * 1000)
            print(f"  AI调用失败 provider=hermes purpose={purpose} returncode={result.returncode} elapsed_ms={elapsed}", flush=True)
            _log_ai_event({
                "provider": "hermes",
                "purpose": purpose,
                "status": "error",
                "returncode": result.returncode,
                "elapsed_ms": elapsed,
                "prompt_chars": len(prompt),
                "stderr_preview": (result.stderr or "")[:180],
            })
            return None
        raw = (result.stdout or "").strip()
        # 去掉 session_id 尾行
        lines = [l for l in raw.splitlines() if not l.startswith("session_id:")]
        out = "\n".join(lines).strip()
        # 去掉可能的引号、markdown fence
        out = out.strip("`'\"")
        if out.startswith("```"):
            out = out.split("```", 2)[1] if "```" in out[3:] else out[3:]
            out = out.strip()
        # 空 或 疑似错误输出
        if not out or len(out) < 4 or len(out) > 400:
            elapsed = int((time.time() - start) * 1000)
            print(f"  AI调用无效 provider=hermes purpose={purpose} elapsed_ms={elapsed} output_chars={len(out)}", flush=True)
            _log_ai_event({
                "provider": "hermes",
                "purpose": purpose,
                "status": "invalid_output",
                "elapsed_ms": elapsed,
                "prompt_chars": len(prompt),
                "output_chars": len(out),
            })
            return None
        elapsed = int((time.time() - start) * 1000)
        print(f"  AI调用成功 provider=hermes purpose={purpose} elapsed_ms={elapsed} output_chars={len(out)}", flush=True)
        _log_ai_event({
            "provider": "hermes",
            "purpose": purpose,
            "status": "ok",
            "elapsed_ms": elapsed,
            "prompt_chars": len(prompt),
            "output_chars": len(out),
            "reply_preview": out[:120],
            "reply_text": out,
        })
        return out
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        print(f"  AI 回复异常 provider=hermes purpose={purpose} elapsed_ms={elapsed}: {e}，fallback 规则引擎", flush=True)
        _log_ai_event({
            "provider": "hermes",
            "purpose": purpose,
            "status": "exception",
            "elapsed_ms": elapsed,
            "prompt_chars": len(prompt),
            "error": str(e)[:180],
        })
        return None


def call_openai_compatible(prompt: str, timeout: int = 60, purpose: str = "reply") -> Optional[str]:
    """调用 OpenAI-compatible chat/completions 后端，如阿里云百炼/Qwen。"""
    if not QWEN_BASE_URL or not QWEN_API_KEY or not QWEN_MODEL:
        print(f"  AI跳过 provider=qwen purpose={purpose} reason=missing_config", flush=True)
        _log_ai_event({
            "provider": "qwen",
            "model": QWEN_MODEL,
            "purpose": purpose,
            "status": "missing_config",
            "base_url_set": bool(QWEN_BASE_URL),
            "api_key_set": bool(QWEN_API_KEY),
            "prompt_chars": len(prompt),
        })
        return None
    url = f"{QWEN_BASE_URL}/chat/completions"
    payload = {
        "model": QWEN_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "你是求职自动回复助手，只输出最终要发给HR的中文短回复，不要解释。",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.4,
        "max_tokens": 220,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {QWEN_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    start = time.time()
    print(f"  AI调用开始 provider=qwen model={QWEN_MODEL} purpose={purpose} prompt_chars={len(prompt)}", flush=True)
    for attempt in range(QWEN_MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="ignore")
            break
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="ignore")[:200]
            if e.code == 429 and attempt < QWEN_MAX_RETRIES:
                delay = _retry_after_seconds(e.headers, QWEN_RETRY_BASE_DELAY * (2 ** attempt), QWEN_RETRY_MAX_DELAY)
                print(f"  Qwen 触发限流，{delay:.1f}s 后重试 ({attempt + 1}/{QWEN_MAX_RETRIES})", flush=True)
                time.sleep(delay)
                continue
            elapsed = int((time.time() - start) * 1000)
            print(f"  Qwen HTTP异常 model={QWEN_MODEL} purpose={purpose} code={e.code} elapsed_ms={elapsed}: {detail}，fallback 规则引擎", flush=True)
            _log_ai_event({
                "provider": "qwen",
                "model": QWEN_MODEL,
                "purpose": purpose,
                "status": "http_error",
                "http_code": e.code,
                "elapsed_ms": elapsed,
                "prompt_chars": len(prompt),
                "error_preview": detail,
            })
            return None
        except Exception as e:
            elapsed = int((time.time() - start) * 1000)
            print(f"  Qwen 调用异常 model={QWEN_MODEL} purpose={purpose} elapsed_ms={elapsed}: {e}，fallback 规则引擎", flush=True)
            _log_ai_event({
                "provider": "qwen",
                "model": QWEN_MODEL,
                "purpose": purpose,
                "status": "exception",
                "elapsed_ms": elapsed,
                "prompt_chars": len(prompt),
                "error": str(e)[:180],
            })
            return None
    try:
        result = json.loads(body)
        choices = result.get("choices") or []
        if not choices:
            elapsed = int((time.time() - start) * 1000)
            print(f"  AI调用无结果 provider=qwen model={QWEN_MODEL} purpose={purpose} elapsed_ms={elapsed}", flush=True)
            _log_ai_event({
                "provider": "qwen",
                "model": QWEN_MODEL,
                "purpose": purpose,
                "status": "empty_choices",
                "elapsed_ms": elapsed,
                "prompt_chars": len(prompt),
            })
            return None
        message = choices[0].get("message") or {}
        out = (message.get("content") or "").strip().strip("`'\"")
        if out.startswith("```"):
            out = out.split("```", 2)[1] if "```" in out[3:] else out[3:]
            out = out.strip()
        if not out or len(out) < 2 or len(out) > 400:
            elapsed = int((time.time() - start) * 1000)
            print(f"  AI调用无效 provider=qwen model={QWEN_MODEL} purpose={purpose} elapsed_ms={elapsed} output_chars={len(out)}", flush=True)
            _log_ai_event({
                "provider": "qwen",
                "model": QWEN_MODEL,
                "purpose": purpose,
                "status": "invalid_output",
                "elapsed_ms": elapsed,
                "prompt_chars": len(prompt),
                "output_chars": len(out),
            })
            return None
        elapsed = int((time.time() - start) * 1000)
        print(f"  AI调用成功 provider=qwen model={QWEN_MODEL} purpose={purpose} elapsed_ms={elapsed} output_chars={len(out)}", flush=True)
        _log_ai_event({
            "provider": "qwen",
            "model": QWEN_MODEL,
            "purpose": purpose,
            "status": "ok",
            "elapsed_ms": elapsed,
            "prompt_chars": len(prompt),
            "output_chars": len(out),
            "reply_preview": out[:120],
            "reply_text": out,
        })
        return out
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        print(f"  Qwen 调用异常 model={QWEN_MODEL} purpose={purpose} elapsed_ms={elapsed}: {e}，fallback 规则引擎", flush=True)
        _log_ai_event({
            "provider": "qwen",
            "model": QWEN_MODEL,
            "purpose": purpose,
            "status": "exception",
            "elapsed_ms": elapsed,
            "prompt_chars": len(prompt),
            "error": str(e)[:180],
        })
        return None


def call_llm(prompt: str, timeout: int = 60, purpose: str = "reply") -> Optional[str]:
    """统一 LLM 入口。默认 Hermes；配置 BOSS_AI_PROVIDER=qwen 时走 OpenAI-compatible。"""
    if AI_PROVIDER in {"qwen", "openai", "openai_compatible"}:
        reply = call_openai_compatible(prompt, timeout=timeout, purpose=purpose)
        if reply:
            return reply
    return call_hermes(prompt, timeout=timeout, purpose=purpose)


def ai_generate(intent: str, messages: list, job_info: dict) -> Optional[str]:
    """主入口：成功返回回复字符串，失败返回 None（调用方用规则引擎 fallback）"""
    if not should_use_ai(intent):
        return None
    prompt = build_prompt(intent, messages, job_info or {})
    reply = call_llm(prompt, purpose=f"reply:{intent}")
    if reply:
        print(f"  AI 生成回复({intent}): {reply}", flush=True)
    return reply


def ai_review_match(job_info: dict, score: int, reason: str, min_score: int = 55) -> Optional[dict]:
    """
    边界分岗位二次判断。
    返回 {"apply": bool, "reason": str}；失败/关闭时返回 None，由规则分继续兜底。
    """
    if not should_use_ai("match_review"):
        return None

    prompt = f"""你是 BOSS 直聘 测试开发/测试负责人 岗位投递筛选助手。判断这个岗位是否值得突破规则分数继续投递。

【我的定位】
{RESUME_BRIEF}

【岗位】
公司：{job_info.get('company','未知')}
职位：{job_info.get('title','未知')}
薪资：{job_info.get('salary','未知')}
标签：{', '.join(job_info.get('tags', []) or [])}
JD节选：{(job_info.get('jd') or '')[:900]}

【规则打分】
score={score}, min_score={min_score}
规则原因：{reason}

判断标准：
- 只在 测试开发 / 测试负责人 / 自动化测试 / 接口测试 / 数据迁移测试 / AI Agent测试 方向值得放行。
- 明显前端、产品、运维、算法、大数据、DBA、纯销售、非技术岗位，不要放行。
- 如果是银行/金融/跨境/大模型测试/质量平台 相关，即使规则分略低也可以放行。
- 输出必须是 JSON，不要 markdown，不要解释。

JSON格式：
{{"apply": true 或 false, "reason": "20字以内中文原因"}}
"""
    out = call_llm(prompt, timeout=45, purpose="match_review")
    if not out:
        return None
    try:
        import re as _re
        m = _re.search(r"\{.*\}", out, _re.S)
        payload = json.loads(m.group(0) if m else out)
        apply = bool(payload.get("apply"))
        review_reason = str(payload.get("reason") or "").strip()
        if not review_reason:
            review_reason = "AI二次判断放行" if apply else "AI二次判断不放行"
        return {"apply": apply, "reason": review_reason[:80]}
    except Exception:
        text = out.strip().lower()
        if text.startswith(("true", "yes", "apply", "投", "放行")):
            return {"apply": True, "reason": out.strip()[:80]}
        if text.startswith(("false", "no", "skip", "不投", "跳过")):
            return {"apply": False, "reason": out.strip()[:80]}
    return None


# === AI 分类器：unknown意图时兜底，让LLM判断真实意图 ===
VALID_INTENTS = [
    "greeting", "ask_salary", "ask_experience", "ask_skills", "ask_education",
    "ask_available", "interview_invite", "ask_resume", "ask_location",
    "ask_project", "rejection", "ask_age", "ask_contact", "ask_tech_detail",
    "ask_outsource", "ask_overtime", "hr_confirm", "hr_ask_status",
    "system_noise", "scam_recruit", "od_outsource", "unknown",
]


def ai_classify(messages: list) -> Optional[str]:
    """
    unknown 兜底分类。把最近对话喂给 Hermes，让它从固定列表里选一个意图标签。
    返回意图字符串或 None（失败时调用方继续按 unknown 处理）。
    """
    if not AI_ENABLED:
        return None
    if not messages:
        return None

    # 只看最近 6 条，重点是 HR 最后一条
    recent = messages[-6:]
    history = ""
    for m in recent:
        role = "HR" if m.get("role") == "hr" else "我"
        history += f"{role}: {m.get('text','').strip()}\n"

    intents_str = ", ".join(VALID_INTENTS)
    prompt = f"""你是BOSS直聘聊天意图分类器。根据对话判断HR最后一条消息的意图，从下列标签里严格选一个：

可选标签：{intents_str}

标签含义速查：
- interview_invite: HR约面试/发时间地点/发会议链接
- ask_resume: HR要简历/附件/联系方式
- ask_tech_detail: HR问具体技术（Redis/Kafka/Spring/分布式...）
- ask_project: HR问做过什么项目/业务
- ask_salary: HR问期望薪资/在职状态
- ask_outsource: HR问能否接受外包/驻场/OD
- ask_overtime: HR问加班/996/工作强度
- hr_ask_status: HR问"在看机会吗/方便聊吗/还在找吗"
- hr_confirm: HR只说"好的/收到/明白"等确认词
- rejection: 公司拒了/岗位不合适/这次不合适
- scam_recruit: 电话销售/网络推广/招商/美业销售等诈骗/骗业务岗
- system_noise: 系统自动提示/通知/招呼语冷启动
- od_outsource: 明确说外包/外派/驻场大厂
- unknown: 实在归不到任何类

【对话】
{history}

输出要求：只输出一个标签词，纯字母下划线，不要任何引号/解释/标点。
"""
    result = call_llm(prompt, timeout=30, purpose="classify")
    if not result:
        return None
    # 清理：取第一个 token
    result = result.strip().split()[0] if result.strip() else ""
    # 只保留字母下划线
    import re as _re
    result = _re.sub(r"[^a-z_]", "", result.lower())
    if result in VALID_INTENTS:
        print(f"  AI分类结果: {result}", flush=True)
        return result
    return None
