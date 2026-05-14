import sys, os
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
WD = str(Path(__file__).resolve().parent)
sys.path.insert(0, WD)
os.chdir(WD)
import reply_engine, ai_reply, chat_monitor, chat_processor
import apply, jd_matcher, conversation_state, followup_engine
from interview_mgr import InterviewManager
from chat_actions import ChatActions
from local_rag import retrieve_context
from manual_review import assess_manual_review
print('IMPORT_OK')

from reply_engine import MessageClassifier

CASES = [
    (u"您好，集团正在招聘销售精英，深圳三家分公司，新人小白好上手", "scam_recruit", "p3b#1 销售拉人"),
    (u"综合月薪范围2到15万不等，一单提成最低40个点", "scam_recruit", "p3b#1b 销售提成"),
    (u"我们这边目前招聘进度比较快，看下你这边什么时候到岗", "ask_available", "p3b#2 招聘进度不再误判noise"),
    (u"你做过支付项目吗", "ask_tech_detail", "p3b#3 做过X吗→tech_detail"),
    (u"做过哪些项目", "ask_project", "p3b#3b 通用项目询问"),
    (u"我们对接了第三方风控系统", "unknown", "p3b#4 第三方对接不再误判外包"),
    (u"能接受外派驻场吗", "ask_outsource", "p3b#4b 真外包仍命中"),
    (u"发份简历看看", "ask_resume", "回归 简历"),
    (u"方便加个微信吗", "ask_contact", "回归 联系方式"),
    (u"明天下午3点来公司面试", "interview_invite", "回归 面试"),
    (u"不太合适，再看看吧", "rejection", "回归 拒绝"),
    (u"好的", "hr_confirm", "回归 确认"),
    (u"共128人投递，你超过63的竞争者", "system_noise", "回归 系统广播"),
    (u"你期望薪资多少K", "ask_salary", "回归 薪资"),
    (u"华为OD岗位考虑吗", "od_outsource", "回归 OD"),
]

passed = failed = 0
fails = []
for hr_text, expected, desc in CASES:
    msgs = [{"role":"hr","text":hr_text}]
    intent = MessageClassifier.classify(msgs)
    ok = intent == expected
    mark = "OK  " if ok else "FAIL"
    print(u"  [{}] {}: got={} want={}".format(mark, desc, intent, expected))
    if ok: passed += 1
    else:
        failed += 1
        fails.append((desc, intent, expected, hr_text))

print("\nRESULT: {} passed / {} failed / {} total".format(passed, failed, len(CASES)))
if fails:
    print("\nFAILURES:")
    for d, g, w, t in fails:
        print(u"  - {}: got={} want={} | text={}".format(d, g, w, t))


print("\nAI_MATCH_REVIEW:")
orig_should_use_ai = apply.should_use_ai
orig_ai_review_match = apply.ai_review_match
try:
    apply.should_use_ai = lambda intent: intent == "match_review"
    apply.ai_review_match = lambda job, score, reason, min_score: {"apply": True, "reason": "大厂AI后端值得投"}
    decision = apply.maybe_ai_override_match(
        {"company": "字节跳动", "title": "后端开发（AI、Agent、推荐系统相关）", "jd": "AI Agent 后端平台"},
        score=53,
        reason="score=53<55 | 核心技术栈+8(agent)",
        min_score=55,
    )
    ok = decision == (True, "AI_REVIEW_PASS: 大厂AI后端值得投")
    print("  [{}] 边界分AI放行".format("OK  " if ok else "FAIL"))
    if ok:
        passed += 1
    else:
        failed += 1

    decision = apply.maybe_ai_override_match(
        {"company": "测试", "title": "前端开发", "jd": "Vue React"},
        score=0,
        reason="HARD_SKIP: title命中排除词 前端",
        min_score=55,
    )
    ok = decision is None
    print("  [{}] 硬过滤不走AI放行".format("OK  " if ok else "FAIL"))
    if ok:
        passed += 1
    else:
        failed += 1
finally:
    apply.should_use_ai = orig_should_use_ai
    apply.ai_review_match = orig_ai_review_match


print("\nINTERVIEW_DEDUPE:")
tmp_dir = Path(WD) / "data" / "_smoke_interview_test"
tmp_dir.mkdir(parents=True, exist_ok=True)
tmp_file = tmp_dir / "interviews.json"
if tmp_file.exists():
    tmp_file.unlink()
mgr = InterviewManager(tmp_dir)
first = mgr.add("测试公司", "测试开发工程师", "李女士", time_str="明天下午3点", raw_msg="明天下午3点来公司面试")
second = mgr.add("测试公司", "测试开发工程师", "李女士", time_str="明天下午3点", raw_msg="明天下午3点来公司面试")
ok = not first.get("_duplicate") and second.get("_duplicate") and len(mgr.interviews) == 1
print("  [{}] 重复面试邀约不重复记录".format("OK  " if ok else "FAIL"))
if ok:
    passed += 1
else:
    failed += 1
if tmp_file.exists():
    tmp_file.unlink()

print("\nRESUME_OPTION_PICKER:")
class _FakeTitle:
    def __init__(self, text):
        self.text = text


class _FakeOption:
    def __init__(self, title, text=""):
        self._title = title
        self.text = text or title

    def ele(self, selector, timeout=0):
        if selector == ".main-title":
            return _FakeTitle(self._title)
        return None


class _FakePage:
    def __init__(self):
        self.global_text_asked = False

    def eles(self, selector, timeout=0):
        if selector == "css:.select-one":
            return [_FakeOption("上传简历"), _FakeOption("发送在线简历")]
        return []

    def ele(self, selector, timeout=0):
        if selector.startswith("text:"):
            self.global_text_asked = True
        return None


fake_page = _FakePage()
picked = ChatActions(fake_page)._find_resume_option("发送在线简历")
ok = picked is not None and picked.text == "发送在线简历" and not fake_page.global_text_asked
print("  [{}] 在线简历只从弹窗选项选择".format("OK  " if ok else "FAIL"))
if ok:
    passed += 1
else:
    failed += 1

print("\nRESUME_CONFIRM_PICKER:")
class _FakeConfirmButton:
    text = "确定"


class _FakeDialog:
    text = "确定向 Boss 发送简历吗？ 取消 确定"

    def ele(self, selector, timeout=0):
        if selector in ("text:确定", "text:确认", "css:.btn-sure", "css:.btn-sure-v2"):
            return _FakeConfirmButton()
        return None


class _FakeConfirmPage:
    def eles(self, selector, timeout=0):
        if selector == "css:.dialog-container":
            return [_FakeDialog()]
        return []


confirm_btn = ChatActions(_FakeConfirmPage())._find_resume_confirm_button(timeout=1)
ok = confirm_btn is not None and confirm_btn.text == "确定"
print("  [{}] 发简历直达确认弹窗可识别".format("OK  " if ok else "FAIL"))
if ok:
    passed += 1
else:
    failed += 1

print("\nLOCAL_RAG:")
rag_text = retrieve_context(
    "greeting",
    [],
    {"title": "测试开发工程师", "jd": "需要Python、Selenium、Requests、MySQL、自动化回归经验", "tags": ["Python", "Selenium"]},
    limit=3,
)
ok = "测试" in rag_text or "自动化" in rag_text or "Python" in rag_text
print("  [{}] RAG上下文可召回测试/自动化资料".format("OK  " if ok else "FAIL"))
if ok:
    passed += 1
else:
    failed += 1

print("\nMANUAL_REVIEW_TAGS:")
MANUAL_CASES = [
    ("ask_identity_info", "方便发一下身份证正反面吗", "high", True, "identity_info"),
    ("ask_identity_info", "需要毕业证编号和学信网截图", "high", True, "certificate_info"),
    ("ask_salary", "你当前薪资多少，最低薪资底线是多少", "high", False, "salary_sensitive"),
    ("interview_invite", "明天下午3点来公司面试", "high", False, "interview_time_confirm"),
    ("ask_outsource", "能接受第三方合同驻场吗", "high", False, "outsource_risk"),
    ("unknown", "这个呢", "low", True, "unknown_low_confidence"),
]
for intent, text, confidence, required, tag in MANUAL_CASES:
    decision = assess_manual_review(intent, text, confidence)
    ok = decision.required == required and decision.tag == tag
    print("  [{}] {}: tag={} required={}".format("OK  " if ok else "FAIL", tag, decision.tag, decision.required))
    if ok:
        passed += 1
    else:
        failed += 1

print("\nAI_REPLY_LOG:")
events = []
orig_call_llm = ai_reply.call_llm
orig_log_ai_event = ai_reply._log_ai_event
try:
    ai_reply.call_llm = lambda prompt, timeout=60, purpose="reply": "完整AI招呼语内容"
    ai_reply._log_ai_event = lambda event: events.append(event)
    ai_reply._log_ai_event({
        "provider": "qwen",
        "purpose": "reply:greeting",
        "status": "ok",
        "reply_preview": "完整AI招呼语内容"[:120],
        "reply_text": "完整AI招呼语内容",
    })
    ok = events and events[-1].get("reply_text") == "完整AI招呼语内容"
    print("  [{}] AI成功日志保留完整reply_text".format("OK  " if ok else "FAIL"))
    if ok:
        passed += 1
    else:
        failed += 1
finally:
    ai_reply.call_llm = orig_call_llm
    ai_reply._log_ai_event = orig_log_ai_event

print("\nFINAL: {} passed / {} failed".format(passed, failed))
if failed:
    raise SystemExit(1)
