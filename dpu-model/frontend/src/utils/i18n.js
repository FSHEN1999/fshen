import { computed } from 'vue'
import { useLangStore } from '../stores/lang.js'

const messages = {
  // ===== 通用 =====
  common: {
    next: { en: 'Next', zh: '下一步' },
    back: { en: 'Back', zh: '返回' },
    save_exit: { en: 'Save and exit', zh: '保存并退出' },
    loading: { en: 'Loading...', zh: '加载中...' },
    network_error: { en: 'Network error, please try again', zh: '网络错误，请重试' },
    info_submitted: { en: 'Information submitted', zh: '信息已提交' },
    info_saved: { en: 'Information saved', zh: '信息已保存' },
  },

  // ===== 页脚 =====
  footer: {
    about: { en: 'About HSBC Express Finance', zh: '关于汇丰快捷融资' },
    terms: { en: 'Platform Terms', zh: '平台条款' },
    privacy: { en: 'Privacy Notice', zh: '隐私声明' },
    hyperlink: { en: 'Hyperlink Policy', zh: '超链接政策' },
    lang_label: { en: 'English', zh: '中文' },
    desc: {
      en: 'This website/application is HSBC Express Finance – a technology platform that connects sellers and lenders. HSBC Express Finance Data Services Limited, a non-banking subsidiary of HSBC, operates HSBC Express Finance and provides services related to the technology platform. HSBC Express Finance is not a lender.',
      zh: '本网站/应用程序为汇丰快捷融资——一个连接卖家和贷方的技术平台。汇丰快捷融资数据服务有限公司是汇丰的非银行子公司，运营汇丰快捷融资并提供与该技术平台相关的服务。汇丰快捷融资并非贷方。',
    },
    copyright: {
      en: '© Copyright. HSBC Express Finance Data Services Limited 2025. All rights reserved.',
      zh: '© 版权所有。汇丰快捷融资数据服务有限公司 2025。保留所有权利。',
    },
  },

  // ===== 登录页 =====
  login: {
    subtitle: { en: 'HSBC Express Finance', zh: '汇丰快捷融资' },
    create_title: { en: 'Create account to start your application', zh: '创建账户以开始您的申请' },
    login_title: { en: 'Log in to your account', zh: '登录您的账户' },
    mobile: { en: 'Mobile number', zh: '手机号码' },
    verify_code: { en: 'Verification code', zh: '验证码' },
    get_code: { en: 'Get code', zh: '获取验证码' },
    password: { en: 'Password', zh: '密码' },
    show: { en: 'Show', zh: '显示' },
    hide: { en: 'Hide', zh: '隐藏' },
    forgot_pwd: { en: 'Forgot password?', zh: '忘记密码？' },
    remember: { en: 'Remember me for 7 days', zh: '7天内自动登录' },
    have_account: { en: 'Already have an account?', zh: '已有账户？' },
    no_account: { en: "Don't have an account?", zh: '没有账户？' },
    log_in: { en: 'Log in', zh: '登录' },
    register: { en: 'Register', zh: '注册' },
    chat: { en: 'Chat with us', zh: '在线咨询' },
    code_sent: { en: 'Code sent', zh: '验证码已发送' },
    login_success: { en: 'Login successful', zh: '登录成功' },
    enter_code: { en: 'Please enter 6-digit code', zh: '请输入6位验证码' },
  },

  // ===== 注册页 =====
  register: {
    title: { en: 'Continue to create profile', zh: '继续创建个人资料' },
    verify_mobile: { en: 'Verify your mobile number', zh: '验证您的手机号码' },
    create_pwd: { en: 'Create password', zh: '创建密码' },
    confirm_pwd: { en: 'Confirm password', zh: '确认密码' },
    pwd_rule_length: { en: 'Contain 8-16 characters', zh: '包含8-16个字符' },
    pwd_rule_letter: { en: 'Contain at least one lower case letter (a-z) and one upper case letter (A-Z)', zh: '至少包含一个小写字母(a-z)和一个大写字母(A-Z)' },
    pwd_rule_number: { en: 'Contain at least one number (0-9)', zh: '至少包含一个数字(0-9)' },
    security_q: { en: 'Security question', zh: '安全问题' },
    security_q_desc: { en: 'Security question will be used to verify your identity in case you forget your password.', zh: '安全问题将用于在您忘记密码时验证您的身份。' },
    select_q: { en: 'Please select a security question', zh: '请选择一个安全问题' },
    q_pet: { en: 'What is the name of your first pet?', zh: '您的第一只宠物叫什么名字？' },
    q_school: { en: 'What is the name of your primary school?', zh: '您的小学叫什么名字？' },
    q_city: { en: 'In which city were you born?', zh: '您出生在哪个城市？' },
    q_book: { en: 'What is your favourite book?', zh: '您最喜欢的书是什么？' },
    enter_answer: { en: 'Please enter your answer', zh: '请输入您的答案' },
    contact_info: { en: 'Contact information', zh: '联系方式' },
    contact_desc: { en: 'Application status will also be sent to below email address.', zh: '申请状态也将发送到以下邮箱地址。' },
    email: { en: 'Email address', zh: '邮箱地址' },
    declaration: { en: 'Declaration', zh: '声明' },
    declaration_text: {
      en: 'By clicking "Sign up", I confirm that I have read, understood and agreed to the',
      zh: '点击"注册"即表示我已阅读、理解并同意',
    },
    terms_link: { en: 'HSBC Express Finance Terms and Conditions', zh: '汇丰快捷融资条款与条件' },
    privacy_link: { en: 'Privacy Notice', zh: '隐私声明' },
    terms_of_use: { en: 'Terms of Use', zh: '使用条款' },
    marketing: { en: 'I agree to receive marketing and promotional materials from HSBC Express Finance.', zh: '我同意接收汇丰快捷融资的营销和推广资料。' },
    have_account: { en: 'Already have an account?', zh: '已有账户？' },
    sign_up: { en: 'Sign up', zh: '注册' },
    success: { en: 'Registration successful, redirecting to login', zh: '注册成功，即将跳转登录' },
    pwd_mismatch: { en: 'Passwords do not match', zh: '两次输入的密码不一致' },
  },

  // ===== Dashboard =====
  dashboard: {
    loan_app: { en: 'Loan application', zh: '贷款申请' },
    loan_repay: { en: 'Loan repayment', zh: '贷款还款' },
    account_settings: { en: 'Account settings', zh: '账户设置' },
    log_out: { en: 'Log out', zh: '退出登录' },
    welcome: { en: 'Welcome to HSBC Express Finance', zh: '欢迎使用汇丰快捷融资' },
    last_login: { en: 'Last login', zh: '上次登录' },
    lending_providers: { en: 'Lending providers', zh: '贷款提供方' },
    pre_approved: { en: 'Pre-approved limit (CNY)', zh: '预批额度（人民币）' },
    feature_fast: { en: 'Draw down funds as fast as 3 minutes', zh: '最快3分钟放款' },
    feature_no_credit: { en: 'No credit report required*', zh: '无需征信报告*' },
    feature_no_fee: { en: '0 admin fees', zh: '零手续费' },
    apply_note: { en: '*For application of CNY', zh: '*适用于人民币' },
    apply_now: { en: 'Apply now', zh: '立即申请' },
    steps_title: { en: '2 steps to activate your offer', zh: '两步激活您的额度' },
    step1_name: { en: 'Submit information', zh: '提交信息' },
    step1_desc: { en: 'Fill in your personal and company information', zh: '填写您的个人及公司信息' },
    step2_name: { en: 'Sign contract', zh: '签署合同' },
    step2_desc: { en: 'Review and sign the loan agreement', zh: '审阅并签署贷款协议' },
    before_apply: { en: 'Before you apply', zh: '申请前须知' },
    required_doc: { en: 'Required document', zh: '所需文件' },
    eligibility: { en: 'Eligibility', zh: '申请资格' },
    product_info: { en: 'Product information', zh: '产品信息' },
    borrow_warning: { en: 'To borrow or not to borrow? Borrow only if you can repay!', zh: '借定唔借？还得到先好借！' },
    // 手风琴内容
    acc_before: {
      en: ['Required document: Hong Kong Identity Card or valid passport', 'Eligibility: Registered business in Hong Kong or Mainland China', 'Product information: Revolving credit facility with flexible repayment terms'],
      zh: ['所需文件：香港身份证或有效护照', '资格要求：在香港或中国大陆注册的企业', '产品信息：循环信贷额度，灵活还款条件'],
    },
    acc_doc: {
      en: ['Valid identification document (ID card / passport)', 'Business registration certificate', 'Proof of company address'],
      zh: ['有效身份证件（身份证/护照）', '营业执照', '公司地址证明'],
    },
    acc_elig: {
      en: ['Business operating for at least 1 year', 'Annual revenue of CNY 500,000 or above', 'No overdue loan records in the past 2 years'],
      zh: ['企业经营至少1年', '年收入50万元人民币及以上', '近2年内无逾期贷款记录'],
    },
    acc_product: {
      en: ['Loan amount: CNY 10,000 - 500,000', 'Loan term: 3 - 36 months', 'Interest rate: From 6.8% p.a.', 'Repayment method: Equal installments'],
      zh: ['贷款金额：人民币1万-50万', '贷款期限：3-36个月', '利率：年化6.8%起', '还款方式：等额分期'],
    },
  },

  // ===== 信息填写页 =====
  info: {
    progress: { en: 'Submit information | Step 1 of 2', zh: '提交信息 | 第1步，共2步' },
    title: { en: 'Business information', zh: '企业信息' },
    subtitle: { en: 'Please provide information on the company applying for the loan. The company must be registered in mainland China.', zh: '请提供申请贷款公司的信息。该公司必须在中国大陆注册。' },
    contact_us: { en: 'No Hong Kong-registered company?', zh: '没有香港注册的公司？' },
    contact_link: { en: 'Contact us', zh: '联系我们' },
    privacy: { en: 'To protect your privacy, all submitted information will only be shared with the lender', zh: '为保护您的隐私，所有提交的信息仅与贷方共享' },
    reg_info: { en: 'Registration information', zh: '注册信息' },
    company_cn: { en: 'Company name in Chinese', zh: '公司中文名称' },
    company_en: { en: 'Company name in English (if any)', zh: '公司英文名称（如有）' },
    credit_code: { en: 'Unified Social Credit Identifier', zh: '统一社会信用代码' },
    enter_credit: { en: 'Enter 18-digit code', zh: '请输入18位代码' },
    biz_ops: { en: 'Business operations', zh: '经营信息' },
    biz_note: { en: 'Please review the following information. If the pre-filled information is incorrect, kindly remove it and select again.', zh: '请核实以下信息。如预填信息有误，请删除后重新选择。' },
    cust_countries: { en: 'Top 3 customer countries/regions', zh: '前3大客户国家/地区' },
    supp_countries: { en: 'Top 3 supplier countries/regions', zh: '前3大供应商国家/地区' },
    funding_country: { en: 'Country/region of funding sources', zh: '资金来源国家/地区' },
    select_country: { en: 'Select country/region', zh: '选择国家/地区' },
    industry: { en: 'Industry', zh: '行业' },
    select_industry: { en: 'Select industry', zh: '选择行业' },
    main_products: { en: 'Main products sold', zh: '主营产品' },
    describe_products: { en: 'Describe your main products', zh: '描述您的主营产品' },
    initial_wealth: { en: 'Initial source of wealth (select all that apply)', zh: '初始财富来源（可多选）' },
    ongoing_income: { en: 'Ongoing sources of wealth and income (select all that apply)', zh: '持续收入和财富来源（可多选）' },
    fund_sources: { en: 'Sources of funds (select all that apply)', zh: '资金来源（可多选）' },
    declaration: {
      en: "By clicking 'Next', you certify that the information uploaded/provided to HSBC Express Finance is true, accurate, complete and not misleading. You agree and acknowledge that HSBC Express Finance may share the information with the lender for the purpose of processing your application.",
      zh: '点击"下一步"即表示您确认向汇丰快捷融资上传/提供的信息是真实、准确、完整且无误导的。您同意并知悉汇丰快捷融资可能会将该信息与贷方共享，以处理您的申请。',
    },
    company_required: { en: 'Company name is required', zh: '公司名称为必填项' },
    credit_required: { en: 'Credit code is required', zh: '信用代码为必填项' },
    credit_18: { en: 'Must be 18 digits', zh: '必须为18位' },
    enter_cn: { en: 'Enter company name in Chinese', zh: '请输入公司中文名称' },
    enter_en: { en: 'Enter company name in English', zh: '请输入公司英文名称' },
  },

  // ===== 复选框选项 =====
  options: {
    biz_income: { en: 'Business income', zh: '经营收入' },
    savings: { en: 'Savings', zh: '储蓄' },
    inheritance: { en: 'Inheritance', zh: '继承' },
    gift: { en: 'Gift', zh: '赠与' },
    other: { en: 'Other', zh: '其他' },
    employ_income: { en: 'Employment income', zh: '就业收入' },
    investments: { en: 'Investments', zh: '投资' },
    rental: { en: 'Rental income', zh: '租金收入' },
    biz_revenue: { en: 'Business revenue', zh: '营业收入' },
    personal_savings: { en: 'Personal savings', zh: '个人储蓄' },
    fi_loans: { en: 'Loans from financial institutions', zh: '金融机构贷款' },
    invest_returns: { en: 'Investment returns', zh: '投资回报' },
  },

  // ===== 行业选项 =====
  industries: {
    ce: { en: 'Consumer Electronics', zh: '消费电子' },
    fa: { en: 'Fashion & Apparel', zh: '时尚服饰' },
    hg: { en: 'Home & Garden', zh: '家居园艺' },
    hb: { en: 'Health & Beauty', zh: '健康美容' },
    fb: { en: 'Food & Beverage', zh: '食品饮料' },
    ie: { en: 'Industrial Equipment', zh: '工业设备' },
    tech: { en: 'Technology', zh: '科技' },
    auto: { en: 'Automotive', zh: '汽车' },
    other: { en: 'Other', zh: '其他' },
  },

  // ===== 股东页 =====
  shareholder: {
    progress: { en: 'Submit information | Step 2 of 2', zh: '提交信息 | 第2步，共2步' },
    title: { en: 'Connected parties information', zh: '关联方信息' },
    subtitle: {
      en: 'The names of all legal representative, shareholders (with equity stakes ≥25%) and directors have been pre-filled based on retrieved data. Please review for accuracy and provide further detail as required.',
      zh: '所有法定代表人、股东（持股比例≥25%）和董事的姓名已根据查询数据预填。请核实准确性并按要求提供更多详细信息。',
    },
    tip: { en: 'Tips: Please make sure that all uploaded files are complete and clear.', zh: '提示：请确保所有上传的文件完整清晰。' },
    incomplete: { en: 'Incomplete', zh: '未完成' },
    complete: { en: 'Complete', zh: '已完成' },
    id_doc_type: { en: 'ID document type', zh: '证件类型' },
    id_prc: { en: 'PRC Resident Identity Card', zh: '中华人民共和国居民身份证' },
    id_travel: { en: 'Mainland Travel Permit for Hong Kong and Macau Residents', zh: '港澳居民来往内地通行证' },
    id_passport: { en: 'Passport', zh: '护照' },
    id_front: { en: 'ID document front side', zh: '证件正面' },
    id_back: { en: 'ID document back side', zh: '证件背面' },
    drag_drop: { en: 'Drag and drop or', zh: '拖拽或' },
    browse: { en: 'browse file', zh: '浏览文件' },
    upload_note: { en: 'Upload up to 1 document. JPG, PNG, JPEG or BMP format under 10MB.', zh: '最多上传1个文件。JPG、PNG、JPEG或BMP格式，小于10MB。' },
    dob: { en: 'Date of birth', zh: '出生日期' },
    nationality: { en: 'Nationality (Country/Region)', zh: '国籍（国家/地区）' },
    select: { en: 'Select', zh: '请选择' },
    mobile: { en: 'Mobile number', zh: '手机号码' },
    enter_mobile: { en: 'Enter mobile number', zh: '请输入手机号码' },
    sign_hint: { en: 'The signing links will be sent to this number', zh: '签署链接将发送至此号码' },
    email: { en: 'Email address', zh: '邮箱地址' },
    enter_email: { en: 'Enter email address', zh: '请输入邮箱地址' },
    email_hint: { en: 'The signing links will be sent to this email address', zh: '签署链接将发送至此邮箱地址' },
    add: { en: 'Add new shareholder (Optional)', zh: '新增股东（可选）' },
    declaration: {
      en: "By clicking 'Next', I/we certify that the information uploaded/provided to HSBC Express Finance Data Services Limited ('HSBC Express Finance') in this form is correct, accurate and complete. I/We acknowledge that such information will be used for this loan application to FundPark and other purposes that HSBC Express Finance deems appropriate.",
      zh: '点击"下一步"即表示本人/我们确认本表格中上传/提供给汇丰快捷融资数据服务有限公司（"汇丰快捷融资"）的信息是正确、准确和完整的。本人/我们知悉该等信息将用于向FundPark的贷款申请及汇丰快捷融资认为适当的其他用途。',
    },
    file_too_large: { en: 'File size must be under 10MB', zh: '文件大小不能超过10MB' },
    role_legal: { en: 'Legal representative', zh: '法定代表人' },
    role_sh_dir: { en: 'Shareholder - Director', zh: '股东-董事' },
    role_sh: { en: 'Shareholder', zh: '股东' },
    role_dir: { en: 'Director', zh: '董事' },
  },

  // ===== 额度页 =====
  quota: {
    calculating: { en: 'Calculating your loan limit...', zh: '正在测算您的借款额度...' },
    blocked: { en: 'Unable to pass qualification assessment', zh: '暂时无法通过资质评估' },
    improve_info: { en: 'Improve personal information', zh: '完善个人信息' },
    your_limit: { en: 'Your estimated loan limit', zh: '您的预估借款额度' },
    repay_period: { en: 'Suggested repayment period', zh: '建议还款周期' },
    months: { en: 'months', zh: '个月' },
    annual_rate: { en: 'Reference annual rate', zh: '参考年利率' },
    risk_level: { en: 'Risk level', zh: '风险等级' },
    risk_suffix: { en: ' risk', zh: '风险' },
    valid_until: { en: 'Valid until', zh: '额度有效期' },
    apply_loan: { en: 'Apply for loan', zh: '立即借款' },
    recalculate: { en: 'Recalculate', zh: '重新测算' },
    go_back: { en: 'Go back', zh: '返回' },
    fill_first: { en: 'Please complete information first', zh: '请先完成信息填写' },
    go_fill: { en: 'Go to fill', zh: '去填写' },
    applied: { en: 'Loan application submitted', zh: '借款申请已提交' },
  },

  // ===== 审批页 =====
  approval: {
    title: { en: 'Application status', zh: '申请状态' },
    approved: { en: 'Approved', zh: '已批准' },
    rejected: { en: 'Rejected', zh: '已拒绝' },
    assessing: { en: 'Assessing', zh: '评估中' },
    approved_desc: { en: 'Your application has been approved. Please proceed to sign the agreement.', zh: '您的申请已获批准。请继续签署协议。' },
    rejected_desc: { en: 'Unfortunately, your application was not approved at this time.', zh: '很遗憾，您的申请此次未获批准。' },
    assessing_desc: { en: 'Your application is being reviewed. This usually takes 1-3 business days.', zh: '您的申请正在审核中。通常需要1-3个工作日。' },
    app_id: { en: 'Application ID', zh: '申请编号' },
    submitted_on: { en: 'Submitted on', zh: '提交时间' },
    loan_amount: { en: 'Loan amount (CNY)', zh: '贷款金额（人民币）' },
    lending_provider: { en: 'Lending provider', zh: '贷款提供方' },
    refresh: { en: 'Refresh status', zh: '刷新状态' },
    cancel_app: { en: 'Cancel application', zh: '取消申请' },
    resubmit: { en: 'Resubmit application', zh: '重新提交申请' },
    submitted: { en: 'Submitted', zh: '已提交' },
    under_review: { en: 'Under review', zh: '审核中' },
    result: { en: 'Result', zh: '结果' },
    back_dash: { en: '← Back to dashboard', zh: '← 返回主页' },
    no_app: { en: 'No application found', zh: '未找到申请' },
    back_dashboard: { en: 'Back to dashboard', zh: '返回主页' },
    cancel_title: { en: 'Cancel application?', zh: '取消申请？' },
    cancel_desc: { en: 'You will need to resubmit your application after cancellation.', zh: '取消后您需要重新提交申请。' },
    go_back: { en: 'Go back', zh: '返回' },
    confirm_cancel: { en: 'Confirm cancel', zh: '确认取消' },
    cancelled: { en: 'Application cancelled', zh: '申请已取消' },
    op_failed: { en: 'Operation failed', zh: '操作失败' },
  },

  // ===== AppHeader =====
  header: {
    logout: { en: 'Log out', zh: '退出登录' },
  },
}

// 翻译函数：t('dashboard.welcome') => 对应语言文本
export function useI18n() {
  const langStore = useLangStore()

  function t(key) {
    const parts = key.split('.')
    let obj = messages
    for (const p of parts) {
      obj = obj?.[p]
      if (!obj) return key
    }
    return obj[langStore.lang] || obj.en || key
  }

  // 用于模板中的计算属性版本
  function tc(key) {
    return computed(() => t(key))
  }

  return { t, tc, lang: langStore.lang, isZh: langStore.isZh, isEn: langStore.isEn }
}
