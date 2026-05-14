"""
智能回复引擎
根据HR消息意图 + 简历信息，生成合适的回复
默认规则匹配 + 模板；高价值意图可选走 AI (BOSS_AI_REPLY=1 开启)
"""
import re
from datetime import datetime
from candidate_profile import load_resume
try:
    from ai_reply import ai_generate, should_use_ai
except Exception:
    def ai_generate(*a, **kw): return None
    def should_use_ai(*a, **kw): return False


# ===== 简历信息：由 .env.local.ps1 / 环境变量注入，避免提交个人隐私 =====
RESUME = load_resume()


class MessageClassifier:
    """消息意图分类器 — 按优先级从高到低排列，精确意图优先于泛意图"""

    # 意图 → 关键词（按优先级排列！靠前的先匹配）
    INTENT_PATTERNS_ORDERED = [
        # === 最高优先级：系统噪音/诈骗/OD外包，直接静默或拒绝 ===
        ("system_noise", [
            # BOSS 系统广播类消息，不是 HR 真人
            r"共\s*\d*\s*人投递", r"超过.*竞争者", r"超过\d+%的",
            r"投递速度", r"岗位已下线", r"该职位已下线",
            r"您的投递正在处理", r"BOSS已收到",
            r"\[投递提醒\]", r"\[系统通知\]", r"\[BOSS提醒\]",
        ]),
        ("scam_recruit", [
            # 兼职/上麦/居家副业/主播等骚扰，一律静默
            r"居家.*兼职", r"兼职.*居家", r"不露脸", r"只需.*上麦",
            r"上麦.*聊天", r"声音.*兼职", r"宝妈.*兼职", r"学生.*兼职",
            r"日结.*[0-9]", r"在家.*副业", r"手机.*兼职",
            r"陪.*聊", r"陪玩", r"语音.*陪",
            r"小姐姐", r"小哥哥", r"小宝",
            r"工资日结", r"时间自由.*兼职",
            # 销售/保险/微商等明显非目标岗的拉人话术
            r"销售精英", r"招聘销售", r"销售.*团队",
            r"综合月薪.*[0-9]+到[0-9]+万", r"月薪.*[0-9]+-[0-9]+万",
            r"新人小白", r"好上手", r"销冠.*亲自带", r"带你做单",
            r"一单提成", r"单量提成", r"提成.*[0-9]+个点",
            r"保险.*代理", r"微商.*加盟", r"招商.*加盟",
            r"主播", r"直播.*带货", r"网红",
        ]),
        ("od_outsource", [
            # 明确识别 OD / 华为 OD / 外企德科派遣 等，礼貌拒绝
            r"华为.*OD", r"OD岗位", r"OD.*岗位", r"社招OD",
            r"外企德科.*派", r"签.*外企德科", r"签在.*外企",
            r"合同.*签在.*德科", r"人力.*派遣.*华为",
            r"OD模式", r"华为社招.*OD",
        ]),
        # === 高优先级：具体动作类 ===
        ("rejection", [
            r"不太合适", r"不匹配", r"不够匹配", r"不符合", r"暂时没有",
            r"已经找到", r"感谢.*投递", r"谢谢.*投递",
            r"不太适合", r"有合适.*再", r"岗位已", r"已满", r"不合适",
            r"已关闭",            r"暂不考虑", r"不太匹配", r"非常抱歉",
            r"与.*不.*匹配", r"暂时不", r"不完全匹配",
            r"抱歉.*更匹配", r"更匹配的候选", r"祝您.*找到", r"祝.*顺利",
            r"抱歉.*不.*合适", r"抱歉.*寻找", r"希望寻找",
            r"有些出入", r"要求.*出入", r"早日找到",
            r"不做重复推荐", r"已有同事.*联系", r"简历非常优秀.*祝",
           r"给不到", r"薪资.*达不到", r"达不到.*要求", r"经验.*不够",
           r"这个薪资", r"预算.*不够", r"预算有限",
            r"打扰了", r"不好意思打扰",
        ]),
        ("interview_invite", [
            r"约[个一].*面", r"来公司[面聊]", r"到公司.*面",
            r"线上面试.*时间", r"视频面试.*时间", r"电话面试.*时间",
            r"笔试", r"机试",
            r"HR面", r"技术面", r"复试", r"终面", r"offer",
            r"约.*面试时间", r"安排.*面试",
            r"邀请.*面试", r"面试邀请", r"参加面试",
            r"下周.*面试", r"明天.*面试", r"今天.*面试",
            r"面试通知", r"面试安排",
        ]),
        ("ask_resume", [
            r"发.*简历", r"[要看]看.*简历", r"简历.*发[一来过]", r"附件",
            r"发[一份]", r"作品", r"Github", r"github",
            r"简历.*看[看一下]", r"传.*简历", r"投.*简历",
            r"求.*简历", r"简历.*[给发求]", r"能求.*简历",
        ]),
        ("ask_identity_info", [
            r"身份证", r"身份证号", r"证件号", r"证件号码",
            r"身份信息", r"身份证正反面", r"身份证照片",
            r"手持身份证", r"实名信息", r"证件信息",
            r"身份编号", r"毕业证编号", r"毕业证书编号", r"学位证编号",
        ]),
        ("ask_contact", [
            r"电话[号码]?[多少]", r"手机号", r"联系方式",
            r"微信[号多]", r"wx", r"WX", r"[加换].*微信", r"[加换].*电话",
            r"留[个一].*[号电微]", r"号码[多少]",
            r"方便电话沟通", r"打个电话",
        ]),
        # === 中优先级：信息询问类 ===
        ("ask_salary", [
            r"期望薪[资资]", r"薪[资资]要求", r"薪[资资].*期望", r"对薪[资资]", r"薪酬",
            r"要[多少].*[Kk万]", r"多少[KkＫ]", r"工资", r"月薪",
            r"税前", r"税后", r"到手", r"package", r"年薪",
            r"期望[多少].*[Kk万]",
        ]),
        ("ask_education", [
            r"学历", r"[什哪]个学校", r"全日制", r"统招", r"学信网",
            r"毕业证", r"学信网截图",
        ]),
        ("ask_experience", [
            r"工作经[验历]", r"做了[几多]年", r"做[几多]年", r"从业", r"工作[了多]年",
            r"之前[做在]", r"上一家",
            r"目前在[做哪]", r"现在[在做]",
            r"多少年经验", r"几年经验", r"干了[几多]年", r"做过几年",
        ]),
        ("ask_skills", [
            r"技术栈", r"会[什哪]么技术", r"熟悉[什哪]", r"掌握",
            r"用过[什哪]", r"了解[什哪]", r"擅长",
            r"有没有.*经验",
        ]),
        ("ask_available", [
            r"什么时候.*到岗", r"到岗时间", r"多久.*入职", r"立即到岗",
            r"什么时候[能可]", r"在职还是", r"离职状态",
            r"离职了吗", r"还在.*上班", r"目前.*状态",
            r"在职.*离职", r"现在.*工作",
            r"面试通过.*到岗", r"能接受.*面试[吗么嘛]",
            r"多久.*到岗", r"目前是离职",
            r"离职原因", r"为什么离", r"离职证明", r"目前离职",
            r"还在职", r"在职吗",
        ]),
        ("ask_age", [
            r"多大", r"年龄", r"哪年[生出]", r"几岁", r"出生",
        ]),
        ("ask_location", [
            r"在哪[里个]", r"住哪", r"深圳[哪那]", r"区域", r"通勤",
            r"能接受.*地点", r"工作地[点址]",
            r"在深圳[吗么嘛]", r"在[哪那]个城市", r"人在[哪那深广上北]",
            r"在上海[吗么嘛]?", r"在北京[吗么嘛]?", r"在广州[吗么嘛]?",
            r"现在在哪", r"目前在哪", r"什么时候回来", r"打算.*来", r"会来.*吗",
            r"在[上北广深成杭].*[吗么嘛]",
        ]),
        ("ask_project", [
            r"项目经[验历]", r"做过[什哪].*项目", r"负责[什哪]", r"项目介绍",
            r"亮点", r"成果", r"业绩",
        ]),
        # === 新增意图 ===
        ("ask_tech_detail", [
            r"涉及.*模块", r"有.*涉及", r"有没有.*开发经", r"做过.*系统吗", r"有.*项目经验",
            r"用过.*框架", r"接触.*多[吗嘛么]",
            r"有.*经验[吗么嘛]", r"熟悉.*[吗么嘛]",
            r"支付.*经验", r"电商.*经验", r"erp", r"ERP", r"中台.*经验",
            r"做过.*开发", r"有没有.*开发",
            r"做过.*(支付|电商|erp|ERP|中台|风控|清算|金融|交易|订单|推荐|搜索|大数据|AI|ai|机器学习|微服务|高并发|分布式).*[吗么嘛]?",
            r"英[语文].*[怎如]", r"英[语文]口语", r"英[语文].*沟通", r"英[语文].*水平",
            r"[多少]问题", r"问几个问题",
        ]),
        ("ask_outsource", [
            r"外包", r"外派", r"驻场", r"人力外包", r"项目外包",
            r"派遣", r"劳务", r"考虑.*外包",
            r"外包.*考虑", r"接受.*外包",
            r"第三方.*派", r"第三方.*用工", r"第三方.*合同",
        ]),
        ("ask_overtime", [
            r"加班", r"工作时间", r"上下班", r"弹性", r"996", r"大小周",
            r"双休", r"单休", r"周末", r"工时",
        ]),
        ("ai_suspect", [
            r"你是ai", r"你是机器人", r"是不是ai", r"是不是机器人",
            r"太像ai", r"像ai", r"不像真人", r"真人吗", r"你是真人吗",
        ]),
        ("hr_ask_status", [
            r"还.*考虑.*机会", r"还.*看.*机会", r"还.*找.*工作",
            r"是否.*考虑.*机会", r"这边.*考虑.*机会",
            r"方便.*聊聊", r"方便.*沟通", r"可以.*聊聊",
            r"还考虑吗", r"还在看吗", r"还找工作吗",
        ]),
        ("hr_confirm", [
            r"^好的$", r"^收到$", r"^嗯嗯$", r"^ok$", r"^OK$",
            r"^了解$", r"^明白$", r"^可以$",
            # 补充：HR简短正向回应（会推进到交换联系方式）
            r"^没问题$", r"^行$", r"^嗯$", r"^好$", r"^OK的$",
            r"简历.*收到", r"已收到.*简历", r"看过.*简历",
            r"挺合适", r"比较合适", r"还不错",  # HR表达积极倾向
        ]),
        # hr_ask_status 合并到 ask_available（回复相同）
        # === 低优先级：泛意图（放最后）===
        ("greeting", [
            r"你好", r"在吗", r"在不在", r"hi$", r"hello", r"您好",
            r"看了.*简历", r"感兴趣", r"聊聊",
            r"方便聊", r"期待.*回复",
            # 注意：移除裸 r"合适" — 它会吞 "您挺合适"(归hr_confirm) 和 "不太合适"(归rejection)
        ]),
    ]


    # HR说"把简历转给负责人/合适再联系"类 — 处于等待状态，不该再发简历
    WAITING_PATTERNS = [
        r"给负责人.*看", r"转.*简历.*负责", r"转.*给.*看", r"合适.*联系", r"有合适.*回复",
        r"合适.*通知", r"如果没有.*通知", r"1个工作日内", r"会和.*沟通",
        r"稍后.*联系", r"我们会.*联系", r"后续.*沟通", r"感谢.*关注",
        r"看一下.*合适", r"审核.*简历", r"查看.*简历.*后",
    ]

    # 非确认类短语——这些短句是正常对话，不是HR在"好的/收到"式确认
    NOT_CONFIRM_PATTERNS = [
        r"卡死", r"难吗", r"没[有呢]", r"什么时候", r"多久", r"几号", r"在[哪上]", r"去[哪上]",
        r"要求", r"条件", r"怎么", r"为什么", r"哪里", r"哪个", r"几点", r"回来",
        r"还是", r"或者", r"不是", r"不对", r"对吗", r"是吗", r"吗$",
    ]

    @classmethod
    def classify(cls, messages: list) -> str:
        """
        根据消息上下文判断意图
        messages: [{"role": "hr"|"me", "text": str}]
        """
        hr_msgs = [m for m in messages if m["role"] == "hr"]
        if not hr_msgs:
            return "unknown"

        last_hr = hr_msgs[-1]["text"]
        last_hr_lower = last_hr.lower()

        # 敏感身份信息优先短路，避免"号码多少"这类词把身份证号误判成联系方式。
        identity_literals = (
            "身份证", "身份证号", "证件号", "证件号码", "身份信息",
            "实名信息", "身份证照片", "身份证正反面", "手持身份证",
            "id card", "national id",
        )
        if any(token in last_hr_lower for token in identity_literals):
            return "ask_identity_info"

        # 上下文：HR是否在等待/转简历状态（此时应静默，不发简历不回复）
        for pat in cls.WAITING_PATTERNS:
            if re.search(pat, last_hr, re.IGNORECASE):
                return "hr_confirm"  # 静默处理

        # 第一轮：先跑完整意图匹配（不再被短消息阈值劫持）
        for intent, patterns in cls.INTENT_PATTERNS_ORDERED:
            for pat in patterns:
                if re.search(pat, last_hr, re.IGNORECASE):
                    return intent

        # 极短消息兜底：未命中任何意图、且 ≤6 字符 且 不含疑问 → hr_confirm
        stripped = last_hr.strip()
        if len(stripped) <= 6:
            for pat in cls.NOT_CONFIRM_PATTERNS:
                if re.search(pat, stripped, re.IGNORECASE):
                    return "unknown"
            return "hr_confirm"

        # 第二轮：扩大到最近2条HR消息（捕获分两条发的情况）
        # ⚠️ 严格过滤：只合并HR的消息，不混入我发的消息（避免我的关键词污染分类）
        if len(hr_msgs) >= 2:
            # hr_msgs 已经是纯 HR 消息列表（第183行过滤），直接合并最后2条
            recent_text = " ".join(m["text"] for m in hr_msgs[-2:])
            for intent, patterns in cls.INTENT_PATTERNS_ORDERED:
                for pat in patterns:
                    if re.search(pat, recent_text, re.IGNORECASE):
                        return intent

        # unknown 时：若对话已深入（我已回复过3条以上），不要再主动推简历，静默
        my_msgs = [m for m in messages if m["role"] == "me"]
        if len(my_msgs) >= 3:
            return "hr_confirm"  # 静默，不乱回

        return "unknown"


class ReplyGenerator:
    """回复生成器"""

    @classmethod
    def generate(cls, intent: str, messages: list = None, job_info: dict = None) -> str:
        """
        根据意图生成回复
        job_info: {"title": "测试开发工程师", "company": "xxx", "salary": "18-30K", "jd": "...", "tags": [...]}
        优先走 AI（若开启且意图在白名单内），失败/关闭则 fallback 规则引擎
        """
        # AI 路径（带 fallback）
        if should_use_ai(intent):
            ai_text = ai_generate(intent, messages or [], job_info or {})
            if ai_text:
                return ai_text
            # 失败则继续走规则

        r = RESUME
        handlers = {
            "greeting": cls._reply_greeting,
            "ask_salary": cls._reply_salary,
            "ask_experience": cls._reply_experience,
            "ask_skills": cls._reply_skills,
            "ask_education": cls._reply_education,
            "ask_available": cls._reply_available,
            "interview_invite": cls._reply_interview,
            "ask_resume": cls._reply_resume,
            "ask_location": cls._reply_location,
            "ask_project": cls._reply_project,
            "rejection": cls._reply_reject,
            "ask_age": cls._reply_age,
            "ask_contact": cls._reply_contact,
            "ask_identity_info": cls._reply_identity_info,
            "ask_tech_detail": cls._reply_tech_detail,
            "ask_outsource": cls._reply_outsource,
            "ask_overtime": cls._reply_overtime,
            "ai_suspect": cls._reply_ai_suspect,
            "hr_confirm": cls._reply_hr_confirm,
            "hr_ask_status": cls._reply_hr_status,
            # 新增三类：噪音/诈骗静默，OD 明确拒绝
            "system_noise": cls._reply_silent,
            "scam_recruit": cls._reply_silent,
            "od_outsource": cls._reply_od_reject,
        }

        handler = handlers.get(intent)
        if handler:
            return handler(r, messages, job_info)
        return cls._reply_default(r, messages, job_info)

    @staticmethod
    def _reply_greeting(r, msgs, job):
        # 瘦身：简短自我介绍+附简历，别啰嗦。HR看了简历自然会问问题。
        return (
            f"您好！{r['experience']}测试开发/测试负责人，熟悉接口自动化、数据库一致性、"
            f"性能压测和上线验证，简历见附件，方便细聊。"
        )

    @staticmethod
    def _reply_salary(r, msgs, job):
        """智能回复——检测HR消息中的多个子问题，一并回答"""
        last_hr = ""
        if msgs:
            hr_msgs = [m for m in msgs if m["role"] == "hr"]
            if hr_msgs:
                last_hr = hr_msgs[-1]["text"]

        parts = [f"我的期望薪资在{r['salary_expect']}范围，具体可以根据岗位职责和整体福利面谈。"]

        # 检测是否同时问了在职状态/到岗时间
        if re.search(r"在职|离职|到岗|入职|多久", last_hr):
            parts.append(f"我目前在职，{r['available']}。")

        # 检测是否同时问了学历
        if re.search(r"学历|学信网|全日制|统招", last_hr):
            parts.append(f"学历是{r['school']}{r['education']}，全日制学信网可查。")

        # 检测是否同时问了面试方式
        if re.search(r"面试方式|现场面试|线[上下]面|远程面|现场远程", last_hr):
            parts.append("面试形式线上线下都可以，时间灵活。")

        return "\n".join(parts)

    @staticmethod
    def _reply_experience(r, msgs, job):
        return (
            f"我有{r['experience']}软件测试与质量工程经验，目前在{r['current_company']}担任{r['current_title']}。\n"
            f"近年主要负责银行及跨境金融系统的功能验证、接口契约校验、数据库一致性核对和自动化回归。\n"
            f"也承担过测试负责人角色，负责测试计划、模块拆解、风险分级和上线验证把关。"
        )

    @staticmethod
    def _reply_skills(r, msgs, job):
        skills_str = "、".join(r["skills"][:8])
        return (
            f"核心能力：{skills_str}等。\n"
            f"熟悉测试设计、接口测试、数据校验、缺陷闭环、JMeter压测和自动化回归。\n"
            f"最近也在结合AI/Agent做测试建模、用例生成和报告自动化。"
        )

    @staticmethod
    def _reply_education(r, msgs, job):
        return f"我是{r['school']} {r['major']}专业 {r['education']}学历，{r['grad_year']}年毕业，全日制。"

    @staticmethod
    def _reply_available(r, msgs, job):
        """智能回复——检测HR消息中的多个子问题，一并回答"""
        last_hr = ""
        if msgs:
            hr_msgs = [m for m in msgs if m["role"] == "hr"]
            if hr_msgs:
                last_hr = hr_msgs[-1]["text"]

        parts = [f"我目前在职，{r['available']}。"]

        # 检测是否同时问了薪资
        if re.search(r"薪[资酬]|期望|多少[Kk万]|工资|月薪", last_hr):
            parts.append(f"期望薪资{r['salary_expect']}，具体可以面谈。")

        # 检测是否同时问了学历
        if re.search(r"学历|学信网|全日制|统招", last_hr):
            parts.append(f"学历是{r['school']}{r['education']}，全日制学信网可查。")

        # 检测是否同时问了面试方式
        if re.search(r"面试方式|现场面试|线[上下]面|远程面", last_hr):
            parts.append("面试形式线上线下都可以，时间灵活。")

        # 检测是否问了离职原因
        if re.search(r"离职原因|为什么离", last_hr):
            parts.append("离职原因是寻求更大的技术挑战和发展空间，希望参与更有深度的项目。")

        # 检测是否问了离职证明
        if re.search(r"离职证明", last_hr):
            parts.append("离职证明入职时可以提供。")

        if len(parts) == 1:
            parts.append("目前在积极看测试开发/测试负责人方向的机会，合适可以尽快安排面试。")

        return "\n".join(parts)

    @staticmethod
    def _reply_interview(r, msgs, job):
        # 面试邀请 - 积极回应
        return (
            f"好的，非常期待！我时间比较灵活，工作日和周末都可以。\n"
            f"请问面试形式是线上还是线下？方便的话把时间和地点发我，我提前安排。"
        )

    @staticmethod
    def _reply_resume(r, msgs, job):
        # 不说废话——系统紧接着真发简历附件，让动作说话
        return "好，简历发您。"

    @staticmethod
    def _reply_contact(r, msgs, job):
        # 这类消息现在交给人工，不自动回复联系方式
        return ""

    @staticmethod
    def _reply_identity_info(r, msgs, job):
        return ""

    @staticmethod
    def _reply_location(r, msgs, job):
        last_hr = ""
        if msgs:
            hr_msgs = [m for m in msgs if m["role"] == "hr"]
            if hr_msgs:
                last_hr = hr_msgs[-1]["text"]
        if re.search(r"什么时候回来|打算.*来|会来.*吗", last_hr):
            return "我目前在深圳，主要看深圳和可远程协作的机会。"
        if re.search(r"在上海|在北京|在广州", last_hr):
            return f"我在深圳，目前在深圳找机会。"
        return f"我目前在深圳，深圳范围内的工作地点都可以接受。"

    @staticmethod
    def _reply_project(r, msgs, job):
        highlights = "\n".join(f"• {h}" for h in RESUME["highlights"])
        return (
            f"主要项目经验：\n{highlights}\n\n"
            f"最核心的是 HSBC 关联 DPU 跨境数字贷款平台测试：覆盖申请、审批、资方接入、客户迁移等核心链路，"
            f"做过接口、数据库、回归和预生产验证。\n"
            f"另一块是银行项目测试交付：负责测试计划、用例设计、执行推进、缺陷闭环和上线验证。"
        )

    @staticmethod
    def _reply_reject(r, msgs, job):
        return "好的，感谢您的反馈！如果后续有合适的测试/质量机会欢迎联系我。祝工作顺利！"

    @staticmethod
    def _reply_age(r, msgs, job):
        return f"我是{r['grad_year']}年毕业的，已经有{r['experience']}工作经验。"

    @staticmethod
    def _reply_tech_detail(r, msgs, job):
        """针对具体技术问题的回复 — 根据HR问的关键词灵活回应"""
        last_hr = ""
        if msgs:
            hr_msgs = [m for m in msgs if m["role"] == "hr"]
            if hr_msgs:
                last_hr = hr_msgs[-1]["text"]

        # 支付相关
        if re.search(r"支付|清算|资金|结算", last_hr):
            return (
                f"有的，我做过银行及跨境金融项目的接口和数据库校验，涉及多系统联调、状态流转和对账核验。\n"
                f"在 DPU 跨境数字贷款平台里也负责过申请、审批、资方接入和客户迁移等核心链路测试。"
            )
        # 电商/中台相关
        if re.search(r"电商|中台|规则引擎|订单", last_hr):
            return (
                f"有相关经验。我做过复杂业务流程的状态流转测试、接口契约校验和数据一致性核对。\n"
                f"如果是中台/订单类系统，也可以从测试建模、异常分支和回归覆盖角度配合。"
            )
        # AI/大模型相关
        if re.search(r"AI|大模型|LLM|NLP|机器学习", last_hr, re.IGNORECASE):
            return (
                f"有的，我会把 AI/Agent 场景拆成测试点、提示词边界、输出结构和异常兜底几层来验证。\n"
                f"也会结合用例生成、日志归因和结果评估，做测试提效和质量闭环。"
            )
        # 通用技术回答
        return (
            f"有相关经验。我的测试能力覆盖测试设计、接口验证、数据库校验、自动化回归和性能测试。\n"
            f"最近项目包括银行/跨境金融测试与DPU平台质量保障，可以根据具体岗位需求详聊～"
        )

    @staticmethod
    def _reply_outsource(r, msgs, job):
        # 用户策略：驻场/外包类直接接受，别问东问西浪费HR耐心
        last_hr = ""
        if msgs:
            hr_msgs = [m for m in msgs if m["role"] == "hr"]
            if hr_msgs:
                last_hr = hr_msgs[-1]["text"]
        # 特别针对"银行驻场"这类具体问法 — 直接肯定
        if re.search(r"银行|金融|券商|保险", last_hr):
            return "可以接受，我之前做过银行及跨境金融项目的测试交付，对业务流程比较熟悉。"
        if re.search(r"驻场", last_hr):
            return "可以接受驻场。"
        if re.search(r"外包|派遣|外派|人力", last_hr):
            return "外包可以接受，主要看项目和测试范围。"
        return "可以接受。"

    @staticmethod
    def _reply_overtime(r, msgs, job):
        # 策略：直接说能接受项目加班、希望工时合理，别反问HR
        return "项目期可以接受必要加班，平时希望工时相对正常。"

    @staticmethod
    def _reply_hr_confirm(r, msgs, job):
        """HR只说'好的/收到'——不必再主动多嘴，静默跳过"""
        # 返回空字符串意味着不回复（由 processor 端检查）
        return ""

    @staticmethod
    def _reply_hr_status(r, msgs, job):
        return "还在看机会，方便沟通。我这边主要看测试开发、自动化测试和质量负责人方向，期待进一步交流。"

    @staticmethod
    def _reply_ai_suspect(r, msgs, job):
        return "不是哈，我这边是本人在沟通。刚才回复写得正式了点，见谅。"

    @staticmethod
    def _reply_silent(r, msgs, job):
        # 系统噪音 / 诈骗骚扰：返回空串，上游 chat_processor 会识别为"静默跳过"
        return ""

    @staticmethod
    def _reply_od_reject(r, msgs, job):
        # OD/外企德科派遣类：礼貌但明确拒绝，避免HR继续推进浪费时间
        return "感谢推荐。OD/派遣模式暂不考虑，谢谢。"

    @staticmethod
    def _reply_default(r, msgs, job):
        # 兜底——不认识的意图，简短确认+留口子，附件简历系统会真发
        return (
            f"收到。{r['experience']}测试开发/测试负责人经验，简历见附件，有具体问题欢迎细聊。"
        )


def classify_and_reply(messages: list, job_info: dict = None) -> dict:
    """
    主入口：分类消息意图 + 生成回复
    Returns: {"intent": str, "reply": str, "confidence": str, "actions": list}

    actions 是回复后需要执行的UI操作列表，可选值：
      - "send_online_resume"  发送在线简历
      - "exchange_phone"      交换电话
      - "exchange_wechat"     交换微信
    """
    intent = MessageClassifier.classify(messages)

    # LLM 兜底分类：规则 unknown 时，让 Hermes 再判一次（最多加1次LLM调用/消息）
    if intent == "unknown":
        try:
            from ai_reply import ai_classify
            llm_intent = ai_classify(messages)
            if llm_intent and llm_intent != "unknown":
                intent = llm_intent
        except Exception:
            pass

    reply = ReplyGenerator.generate(intent, messages, job_info)
    
    # 置信度
    if intent in ("rejection",):
        confidence = "high"  # 拒绝不需要回复太多
    elif intent == "unknown":
        confidence = "low"
    else:
        confidence = "high"

    # 根据意图决定附加动作
    actions = _intent_actions(intent)

    return {
        "intent": intent,
        "reply": reply,
        "confidence": confidence,
        "actions": actions,
    }


# 意图 -> 自动动作映射（分阶段策略——先了解意向再推联系方式）
# 设计原则：
#   1) 第1轮接触（greeting/ask_resume）只发简历，别一上来就骚扰要电话要微信
#   2) HR问具体问题（薪资/经验/技能/项目/技术/外包/地点/加班）→ 只专心回答，不带动作。
#      这些场景HR在评估你，粘上一堆交换请求会显得急切、不专业。
#   3) HR要身份证/证件信息(ask_identity_info) → 只回复走安全渠道，不发送敏感信息
    #   4) HR明确要联系方式(ask_contact) → 人工接管，不自动交换
#   5) HR要安排面试(interview_invite) → 推电话+微信（落实面试时间需要）
#   6) HR确认类(hr_confirm)"好的/收到/明白" → 推电话+微信（此时已热聊，可推进）
#   7) HR问到岗/离职时间(ask_available) → 是HR在评估，只答别推
#   8) rejection → 什么都不推
_ACTION_MAP = {
    # --- 初次接触：默认只发在线简历。附件PDF需显式开启 BOSS_ALLOW_UPLOAD_RESUME=1 ---
    "greeting":           ["send_online_resume"],
    "ask_resume":         ["send_online_resume"],
    "unknown":            [],                                       # 未知意图：静默，不乱发简历

    # --- HR在评估，专注答题，别骚扰 ---
    "ask_salary":         [],
    "ask_experience":     [],
    "ask_skills":         [],
    "ask_education":      [],
    "ask_available":      [],
    "ask_project":        [],
    "ask_identity_info":  [],
    "ask_tech_detail":    [],
    "ask_outsource":      [],  # 外包要先问清再决定，别硬推
    "ask_location":       [],
    "ask_age":            [],
    "ask_overtime":       [],
    "hr_ask_status":      [],

    # --- HR要联系方式：按需交换 ---
    "ask_contact":        [],

    # --- HR已表明推进意向：推电话+微信 ---
    "interview_invite":   ["exchange_phone", "exchange_wechat"],   # 面试邀约，要电话落实
    "hr_confirm":         ["exchange_phone", "exchange_wechat"],   # HR"好的/收到"=热聊，推进
    # rejection: 不在MAP里 = 不执行任何动作
}

def _intent_actions(intent: str) -> list:
    """根据意图返回需要执行的UI动作列表"""
    return _ACTION_MAP.get(intent, [])
