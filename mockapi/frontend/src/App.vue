<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import {
  ArrowDown,
  ArrowRight,
  Check,
  Connection,
  Cpu,
  Delete,
  Document,
  Expand,
  Fold,
  Link,
  Monitor,
  Moon,
  Promotion,
  Refresh,
  Sunny,
  ChatDotRound,
  ChatLineRound,
  Position,
  Search,
  SwitchButton,
  Tickets,
  User,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, ElNotification } from 'element-plus'
import {
  connectSession,
  createContactIssue,
  deleteContactIssueApi,
  disconnectSession,
  fetchEnums,
  fetchHealth,
  fetchContactIssues,
  fetchDowsureMerchantAccounts,
  fetchLogs,
  fetchPspAuthorizationRows,
  fetchSessions,
  loginUser,
  registerAccount,
  registerAndRunMultiShop,
  registerUser,
  replyContactIssueApi,
  runScenarioApi,
  runMockOperation,
  sendAiChat,
} from './api.js'

const defaultEnvironments = ['sit', 'uat', 'dev', 'preprod', 'reg', 'local']
const defaultAiSqlDataSources = ['sit', 'uat', 'dev', 'preprod', 'reg', 'local', 'jastick', 'douke', 'dowsure']
const defaultJourneys = ['200K', '500K', '2000K']
const defaultCurrencies = ['USD', 'CNY']
const defaultFunderResources = ['FUNDPARK', 'HSBC', 'DOWSURE']
const journeyLabels = {
  '200K': 'tier 1',
  '500K': 'tier 2',
  '2000K': 'tier 3',
}

const health = ref('checking')
const loadingHealth = ref(false)
const loadingEnums = ref(false)
const connecting = ref(false)
const registering = ref(false)
const registeringAndBinding = ref(false)
const disconnecting = ref(false)
const loadingSessions = ref(false)
const runningOperationKey = ref('')
const enumOptions = ref(null)
const activeOperationKey = ref('')
const activeSessionId = ref('')
const selectedApplicationUniqueId = ref('')
const dowsureMerchantAccounts = ref([])
const loadingDowsureMerchantAccounts = ref(false)
const pspAuthorizationRows = ref([])
const loadingPspAuthorizationRows = ref(false)
const selectedPspMerchantAccountId = ref('')
const pspSelectionTouched = ref(false)
const operationResults = reactive({})
const liveSessions = ref([])
const eventLogs = ref([])
const activityFeed = ref([])
const registerResult = ref(null)
const registerAutoConnected = ref(false)
const wsConnected = ref(false)
const wsError = ref('')
const darkMode = ref(false)
const toolRailCollapsed = ref(false)
const toolRailOpen = ref(false)
const aiExecutionEnv = ref('sit')
const aiMessages = ref([])
const aiInput = ref('')
const aiSending = ref(false)
const aiError = ref('')
const currentView = ref('console')
const logSearchLoading = ref(false)
const logSearchResults = ref([])
const authStorageKey = 'mockapi-auth-user'
const authUser = ref(null)
const loginError = ref('')
const registerError = ref('')
const authMode = ref('login')

const loginForm = reactive({
  username: '',
  password: '',
})

const userRegisterForm = reactive({
  username: '',
  password: '',
  answer: '',
})

const captchaChallenge = reactive({
  left: 3,
  right: 3,
})

const logSearchForm = reactive({
  keyword: '',
  timeRange: [],
  limit: 500,
})

const contactForm = reactive({
  issue: '',
})
const contactAdminForm = reactive({
  username: '',
  password: '',
  reply: '',
})
const contactAdminLoggedIn = ref(false)
const contactAdminError = ref('')
const contactIssues = ref([])
const interfaceStepEnabled = reactive({})
const activeInterfaceScenarioKey = ref('fpUsd500k')
const activeScenarioTab = ref('steps')
const scenarioSaveState = ref('已保存')
const scenarioExecuting = ref(false)
const scenarioExecutionHistory = ref([])
const scenarioStepResults = reactive({})
const expandedScenarioSteps = reactive({})
const scenarioStepDetailTabs = reactive({})
const latestScenarioRunContext = ref(null)
const scenarioHistoryDetailVisible = ref(false)
const selectedScenarioHistoryRecord = ref(null)
const scenarioAssertions = ref([
  { target: 'HTTP 状态码', rule: '等于 200', enabled: true },
  { target: '响应体 success', rule: '等于 true', enabled: true },
  { target: '业务 traceId', rule: '存在且非空', enabled: true },
])
const scenarioVariables = reactive({
  phone_number: '${phone_number}',
  session_id: '${session_id}',
  merchant_id: '${merchant_id}',
  platform_offer_id: '${platform_offer_id}',
  application_unique_id: '${application_unique_id}',
  limit_application_unique_id: '${limit_application_unique_id}',
  lender_approved_offer_id: '${lender_approved_offer_id}',
})
const scenarioSettings = reactive({
  stopOnFailure: true,
  saveResponse: true,
  validateSession: false,
  timeout: '30s',
})

const scenarioHistoryStorageKey = 'mockapi-scenario-execution-history'

const connectionForm = reactive({
  env: 'reg',
  phone_number: '',
})

const registerForm = reactive({
  env: 'reg',
  journey: '500K',
  currency: 'USD',
  funder_resource: 'FUNDPARK',
  offline: false,
})

const operationForms = reactive({
  linkSp3pl: {},
  underwritten: { amount: 500000, status: 'APPROVED' },
  underwrittenDowsure: { status: 'APPROVED', merchant_accounts: [] },
  dowsureCreditResult: { application_code: '', amount: 500000 },
  dowsureEsignDrawdownResult: {
    application_code: '',
    credit_contract_no: '',
    amount: 100000,
    processing_fee: 0,
  },
  dowsureRepaymentResult: {
    application_code: '',
    loan_code: '',
    payment_principal: 1000,
    payment_interest: 0,
    payment_overdue_interest: 0,
    deal_amount: 1000,
    surplus_principal: 0,
  },
  dowsureRetryCallback: {},
  approvedOffer: { amount: 500000, status: 'APPROVED', failure_reason_index: 1, rejection_reason: 'fraud' },
  pspStart: { status: 'PROCESSING' },
  pspCompleted: { status: 'SUCCESS' },
  esign: { signed_amount: 500000, status: 'SUCCESS' },
  drawdown: { amount: 100000, status: 'APPROVED', failure_reason_index: 1 },
  repaymentStart: { principal_amount: 1000, outstanding_amount: 0 },
  repayment: { principal_amount: 1000, outstanding_amount: 0, status: 'Success', failure_reason_index: 1 },
  multiShopBinding: { state: '' },
  spStatusUpdate: { platform_seller_id: '', status: 'SUCCESS', failure_reason_index: 1 },
  multiShop3plRedirect: {},
  systemEvent: {
    event_type: 'EXCEPTION-APPLICATION-CREATION',
    application_unique_id: '',
    error_code: 'B-6003',
  },
  applicationAbandon: { abandon_reason: 'SellerCancelled' },
  pspHsbcStart: {},
  pspHsbcCompleted: { result: 'SUCCESS' },
})

let logSocket = null
let sessionPollTimer = null

const reasonOptions = computed(() => enumOptions.value?.returned_failure_reasons ?? [])
const approvedRejectionOptions = computed(() => enumOptions.value?.approved_rejection_reasons ?? [])
const drawdownReasonOptions = computed(() => enumOptions.value?.drawdown_failure_reasons ?? [])
const repaymentReasonOptions = computed(() => enumOptions.value?.repayment_failure_reasons ?? [])
const spFailureOptions = computed(() => enumOptions.value?.sp_update_failure_reasons ?? [])
const applicationAbandonOptions = computed(() => enumOptions.value?.application_abandon_reasons ?? [])
const aiSqlDataSources = computed(() => enumOptions.value?.ai_sql_data_sources ?? defaultAiSqlDataSources)
const pendingContactIssuesCount = computed(() => contactIssues.value.filter((item) => item.status !== '已回复').length)
const repliedContactIssuesCount = computed(() => contactIssues.value.filter((item) => item.status === '已回复').length)
const pendingContactIssues = computed(() => contactIssues.value.filter((item) => item.status !== '已回复'))
const isAuthenticated = computed(() => Boolean(authUser.value))
const isAdmin = computed(() => authUser.value?.role === 'admin')
const authDisplayName = computed(() => authUser.value?.username || '未登录')
const authRoleLabel = computed(() => (isAdmin.value ? '管理员账号' : '普通账号'))
const activeToolModule = computed(() => {
  if (currentView.value === 'interfaceTest') return 'interfaceTest'
  if (currentView.value === 'logs') return 'logs'
  if (currentView.value === 'ai') return 'ai'
  if (currentView.value === 'about') return 'about'
  if (currentView.value === 'contact') return 'contact'
  if (currentView.value === 'contactAdmin') return 'contactAdmin'
  return ''
})

const sessionSummary = computed(() => {
  const current = liveSessions.value.find((item) => item.session_id === activeSessionId.value)
  if (current) return current
  if (registerResult.value?.session?.session_id === activeSessionId.value) return registerResult.value.session
  return activityFeed.value.find((item) => item.kind === 'connect')?.payload ?? null
})

const activeOperation = computed(() => (
  operations.value.find((item) => item.key === activeOperationKey.value) ?? null
))

const interfaceTestOperation = computed(() => (
  operations.value.find((item) => item.key === activeOperationKey.value) ?? null
))

const interfaceTestPayloadPreview = computed(() => {
  if (!interfaceTestOperation.value) {
    return selectedInterfaceStep.value?.payload ?? {}
  }
  return buildPayload(interfaceTestOperation.value)
})

const interfaceScenarios = computed(() => [
  {
    key: 'fpUsd500k',
    code: '100132',
    name: 'FP-USD-500K',
    priority: 'P0',
    description: '完整 FP USD 500K 接口自动化场景',
    steps: buildFpUsdScenarioSteps('500K'),
  },
  {
    key: 'fpUsd2k',
    code: '100133',
    name: 'FP-USD-2K',
    priority: 'P0',
    description: '完整 FP USD 2K 接口自动化场景',
    steps: buildFpUsdScenarioSteps('2K'),
  },
  {
    key: 'dsCny',
    code: '100134',
    name: 'DS-CNY',
    priority: 'P0',
    description: 'DS CNY 注册绑店后创建申请单并提交企业/法人信息',
    bootstrap: { env: 'uat', currency: 'CNY', funder_resource: 'DOWSURE', offline: true },
    steps: buildDsCnyScenarioSteps(),
  },
])

const activeInterfaceScenario = computed(() => (
  interfaceScenarios.value.find((item) => item.key === activeInterfaceScenarioKey.value)
  ?? interfaceScenarios.value[0]
))

const interfaceAutomationSteps = computed(() => activeInterfaceScenario.value.steps.map((step, index) => ({
  ...step,
  order: index + 1,
  operation: step.operationKey ? operations.value.find((item) => item.key === step.operationKey) : null,
  enabled: interfaceStepEnabled[step.key] !== false,
})))

const selectedInterfaceStep = computed(() => (
  interfaceAutomationSteps.value.find((step) => step.key === activeOperationKey.value)
  ?? interfaceAutomationSteps.value[0]
  ?? null
))

const enabledInterfaceStepCount = computed(() => (
  interfaceAutomationSteps.value.filter((step) => step.enabled).length
))

const scenarioTabs = [
  { key: 'base', label: '基本信息' },
  { key: 'steps', label: '步骤' },
  { key: 'params', label: '参数' },
  { key: 'hooks', label: '前/后置' },
  { key: 'assertions', label: '断言' },
  { key: 'history', label: '执行历史' },
  { key: 'settings', label: '设置' },
]

const applicationOptions = computed(() => sessionSummary.value?.applications ?? [])

const selectedApplication = computed(() => (
  applicationOptions.value.find((item) => item.application_unique_id === selectedApplicationUniqueId.value)
  ?? applicationOptions.value[0]
  ?? null
))

const selectedApplicationCurrency = computed(() => (
  selectedApplication.value?.finance_product_currency
  || sessionSummary.value?.finance_product_currency
  || sessionSummary.value?.preferred_currency
  || '-'
))

const shouldShowPspAuthorizationRows = computed(() => (
  ['pspStart', 'pspCompleted', 'pspHsbcStart', 'pspHsbcCompleted'].includes(activeOperation.value?.key)
))

const shouldShowDowsureMerchantAccounts = computed(() => (
  activeOperation.value?.key === 'underwrittenDowsure'
))

const consoleStatusCards = computed(() => [
  {
    label: 'API',
    value: health.value === 'ok' ? '正常' : '异常',
    detail: health.value === 'ok' ? 'health check passed' : String(health.value || 'checking'),
    tone: health.value === 'ok' ? 'success' : 'error',
  },
  {
    label: 'Session',
    value: activeSessionId.value ? '已连接' : '未连接',
    detail: activeSessionId.value ? activeSessionId.value : '先连接 session 再执行 mock',
    tone: activeSessionId.value ? 'success' : 'warning',
  },
  {
    label: 'Env',
    value: sessionSummary.value?.env || connectionForm.env,
    detail: sessionSummary.value?.phone_number || '当前选择环境',
    tone: 'info',
  },
  {
    label: 'Logs',
    value: wsConnected.value ? '实时' : '未连接',
    detail: wsError.value || String(eventLogs.value.length) + ' 条缓存日志',
    tone: wsConnected.value ? 'success' : 'warning',
  },
])

const logStatusText = computed(() => {
  if (!activeSessionId.value) return '未连接会话'
  if (wsConnected.value) return '实时日志已连接'
  if (wsError.value) return '日志连接异常: ' + wsError.value
  return '日志连接中'
})

const registerStatusMessage = computed(() => {
  if (!registerResult.value) return ''
  return registerAutoConnected.value
    ? '已自动连接到新注册账号，可以直接执行 mock 操作。'
    : '注册已完成，但还没有可用会话，请点击连接 session 继续。'
})

const operations = computed(() => [
  { key: 'multiShopBinding', title: '多店铺 SP 绑定', icon: Link, endpoint: '/api/mock/multi-shop-binding', description: '输入 state，获取 SP 授权 URL。', fields: [{ prop: 'state', label: 'State', type: 'text', placeholder: '请输入 state' }] },
  { key: 'spStatusUpdate', title: 'SP 状态更新', icon: Cpu, endpoint: '/api/mock/sp-status-update', description: '更新 SP 状态。', fields: [
    { prop: 'platform_seller_id', label: 'Platform Seller ID', type: 'text', placeholder: '可为空，默认使用当前 session' },
    { prop: 'status', label: '状态', type: 'select', options: ['SUCCESS', 'FAIL'] },
    { prop: 'failure_reason_index', label: '失败原因', type: 'select', options: spFailureOptions.value.map((item) => ({ label: item.label, value: item.index })), visible: (form) => form.status === 'FAIL' },
  ] },
  { key: 'multiShop3plRedirect', title: '多店铺 3PL Redirect', icon: Link, endpoint: '/api/mock/multi-shop-3pl-redirect', description: '生成 3PL 跳转 URL。', fields: [] },
  { key: 'linkSp3pl', title: 'SP-3PL 关联', icon: Link, endpoint: '/api/mock/link-sp-3pl', description: '根据当前会话手机号触发 SP 与 3PL 店铺关联。', fields: [] },
  { key: 'underwritten', title: '核保', icon: Document, endpoint: '/api/mock/underwritten', description: '提交核保额度和状态。', fields: [
    { prop: 'amount', label: '核保额度', type: 'number', min: 1, step: 1000 },
    { prop: 'status', label: '状态', type: 'select', options: enumOptions.value?.underwritten_statuses ?? [] },
  ] },
  { key: 'underwrittenDowsure', title: '核保 DOWSURE', icon: Document, endpoint: '/api/mock/underwritten-dowsure', description: '发送 DOWSURE underwrittenLimit.completed。', fields: [
    { prop: 'status', label: '状态', type: 'select', options: enumOptions.value?.underwritten_statuses ?? [] },
  ] },
  { key: 'dowsureCreditResult', title: '授信结果 DOWSURE', icon: Check, endpoint: '/api/mock/dowsure-credit-result', description: '发送 DOWSURE credit-result。', fields: [
    { prop: 'application_code', label: 'Application Code', type: 'text', placeholder: '请输入 applicationCode' },
    { prop: 'amount', label: '授信金额', type: 'number', min: 0.01, step: 1000 },
  ] },
  { key: 'dowsureEsignDrawdownResult', title: 'eSign&drawdown DOWSURE', icon: Promotion, endpoint: '/api/mock/dowsure-esign-drawdown-result', description: '发送 DOWSURE loan 结果。', fields: [
    { prop: 'application_code', label: 'Application Code', type: 'text', placeholder: '可为空，默认使用授信结果' },
    { prop: 'credit_contract_no', label: 'Credit Contract No', type: 'text', placeholder: '可为空，默认使用授信结果' },
    { prop: 'amount', label: '放款金额', type: 'number', min: 0.01, step: 1000 },
    { prop: 'processing_fee', label: 'Processing Fee', type: 'number', min: 0, step: 100 },
  ] },
  { key: 'dowsureRepaymentResult', title: '还款结果 DOWSURE', icon: Refresh, endpoint: '/api/mock/dowsure-repayment-result', description: '发送 DOWSURE repayment 结果。', fields: [
    { prop: 'application_code', label: 'Application Code', type: 'text', placeholder: '可为空，默认使用授信结果' },
    { prop: 'loan_code', label: 'Loan Code', type: 'text', placeholder: '可为空，默认使用 eSign&drawdown 结果' },
    { prop: 'payment_principal', label: 'Payment Principal', type: 'number', min: 0, step: 100 },
    { prop: 'payment_interest', label: 'Payment Interest', type: 'number', min: 0, step: 100 },
    { prop: 'payment_overdue_interest', label: 'Overdue Interest', type: 'number', min: 0, step: 100 },
    { prop: 'deal_amount', label: 'Deal Amount', type: 'number', min: 0, step: 100 },
    { prop: 'surplus_principal', label: 'Surplus Principal', type: 'number', min: 0, step: 100 },
  ] },
  { key: 'dowsureRetryCallback', title: '重试请求 DOWSURE', icon: Refresh, endpoint: '/api/mock/dowsure-retry-callback', description: '调用 DOWSURE callback retry，limit=100。', fields: [] },
  { key: 'approvedOffer', title: '审批', icon: Check, endpoint: '/api/mock/approved-offer', description: '发送审批额度、状态和原因。', fields: [
    { prop: 'amount', label: '审批金额', type: 'number', min: 1, step: 1000 },
    { prop: 'status', label: '状态', type: 'select', options: enumOptions.value?.approved_offer_statuses ?? [] },
    { prop: 'failure_reason_index', label: '退回原因', type: 'select', options: reasonOptions.value.map((item) => ({ label: item.label, value: item.index })), visible: (form) => form.status === 'RETURNED' },
    { prop: 'rejection_reason', label: '拒绝原因', type: 'select', options: approvedRejectionOptions.value.map((item) => ({ label: item.label, value: item.value })), visible: (form) => form.status === 'REJECTED' },
  ] },
  { key: 'pspStart', title: 'PSP 开始', icon: Promotion, endpoint: '/api/mock/psp-start', description: '发送 PSP started 状态。', fields: [{ prop: 'status', label: '状态', type: 'select', options: enumOptions.value?.psp_start_statuses ?? [] }] },
  { key: 'pspCompleted', title: 'PSP 完成', icon: Check, endpoint: '/api/mock/psp-completed', description: '发送 PSP completed 状态。', fields: [{ prop: 'status', label: '状态', type: 'select', options: enumOptions.value?.psp_completed_statuses ?? [] }] },
  { key: 'esign', title: '电子签', icon: Document, endpoint: '/api/mock/esign', description: '发送签约金额和签约结果。', fields: [
    { prop: 'signed_amount', label: '签约金额', type: 'number', min: 1, step: 1000 },
    { prop: 'status', label: '状态', type: 'select', options: enumOptions.value?.esign_statuses ?? [] },
  ] },
  { key: 'drawdown', title: '放款', icon: Promotion, endpoint: '/api/mock/drawdown', description: '提交放款金额、状态和失败原因。', fields: [
    { prop: 'amount', label: '放款金额', type: 'number', min: 0.01, step: 1000 },
    { prop: 'status', label: '状态', type: 'select', options: enumOptions.value?.drawdown_statuses ?? [] },
    { prop: 'failure_reason_index', label: '失败原因', type: 'select', options: drawdownReasonOptions.value.map((item) => ({ label: `${item.code} ${item.label}`, value: item.index })), visible: (form) => form.status === 'REJECTED' },
  ] },
  { key: 'repaymentStart', title: '还款开始', icon: Refresh, endpoint: '/api/mock/repayment-start', description: '发送还款开始通知。', fields: [
    { prop: 'principal_amount', label: '本金', type: 'number', min: 0.01, step: 100 },
    { prop: 'outstanding_amount', label: '剩余金额', type: 'number', min: 0, step: 100 },
  ] },
  { key: 'repayment', title: '还款结果', icon: Refresh, endpoint: '/api/mock/repayment', description: '发送还款结果和失败原因。', fields: [
    { prop: 'principal_amount', label: '本金', type: 'number', min: 0.01, step: 100 },
    { prop: 'outstanding_amount', label: '剩余金额', type: 'number', min: 0, step: 100 },
    { prop: 'status', label: '状态', type: 'select', options: enumOptions.value?.repayment_statuses ?? [] },
    { prop: 'failure_reason_index', label: '失败原因', type: 'select', options: repaymentReasonOptions.value.map((item) => ({ label: `${item.code} ${item.label}`, value: item.index })), visible: (form) => form.status === 'Failure' },
  ] },
  { key: 'systemEvent', title: '系统事件通知', icon: Monitor, endpoint: '/api/mock/system-event', description: '发送 system events 通知。', fields: [
    { prop: 'event_type', label: '事件类型', type: 'select', options: enumOptions.value?.system_event_types ?? [] },
    { prop: 'application_unique_id', label: 'Application Unique ID', type: 'text', placeholder: '可为空，使用当前会话' },
    { prop: 'error_code', label: '错误码', type: 'select', options: ['B-6003', 'B-6005'], visible: (form) => form.event_type === 'EXCEPTION-APPLICATION-CREATION' },
  ] },
  { key: 'applicationAbandon', title: 'Abandon', icon: Monitor, endpoint: '/api/mock/application-abandon', description: '发送 application.status Abandoned 通知。', fields: [
    { prop: 'abandon_reason', label: 'Abandon Reason', type: 'select', options: applicationAbandonOptions.value.map((item) => ({ label: item.label, value: item.value })) },
  ] },
  { key: 'pspHsbcStart', title: 'PSP 开始 HSBC', icon: Promotion, endpoint: '/api/mock/psp-hsbc-start', description: '发送 HSBC PSP started 通知。', fields: [] },
  { key: 'pspHsbcCompleted', title: 'PSP 完成 HSBC', icon: Check, endpoint: '/api/mock/psp-hsbc-completed', description: '发送 HSBC PSP completed 通知。', fields: [{ prop: 'result', label: '结果', type: 'select', options: ['SUCCESS', 'FAIL'] }] },
])

function buildFpUsdScenarioSteps(limitLabel) {
  const offerName = limitLabel === '2K' ? '选择offer额度-2k' : '选择offer额度-500k'
  return [
    { key: `${limitLabel}-sms`, type: 'flow', method: 'FLOW', kind: '场景步骤', title: '发送注册短信', endpoint: 'flow: register-and-run-multishop' },
    { key: `${limitLabel}-token`, type: 'flow', method: 'FLOW', kind: '场景步骤', title: '验证码调用验证生成一次token', endpoint: 'flow: register-and-run-multishop' },
    { key: `${limitLabel}-signup`, type: 'flow', method: 'FLOW', kind: '场景步骤', title: '用户注册', endpoint: 'flow: register-and-run-multishop' },
    { key: `${limitLabel}-state`, type: 'flow', method: 'FLOW', kind: '场景步骤', title: '生成state做sp', endpoint: 'flow: register-and-run-multishop' },
    { key: `${limitLabel}-sp-auth`, type: 'flow', method: 'FLOW', kind: '场景步骤', title: '进行SP授权', endpoint: 'flow: register-and-run-multishop' },
    { key: `${limitLabel}-update-offer`, type: 'flow', method: 'FLOW', kind: '场景步骤', title: 'sp-updateOffer(成功)', endpoint: 'flow: register-and-run-multishop' },
    { key: `${limitLabel}-3pl-auth`, type: 'flow', method: 'FLOW', kind: '场景步骤', title: '亚马逊3PL授权', endpoint: 'flow: register-and-run-multishop' },
    { key: `${limitLabel}-3pl-auth-result`, type: 'flow', method: 'FLOW', kind: '场景步骤', title: '3PL AUTH授权', endpoint: 'flow: register-and-run-multishop' },
    { key: `${limitLabel}-application`, type: 'api', method: 'POST', kind: '自定义请求', title: '创建申请单', endpoint: '/api/mock/create-application-context', operationKey: null, payload: { journey: limitLabel === '2K' ? '200K' : '500K' } },
    { key: `${limitLabel}-business-info`, type: 'api', method: 'POST', kind: '自定义请求', title: '邓白氏提交企业信息', endpoint: '/api/mock/fp-business-profile', operationKey: null, payload: { journey: limitLabel === '2K' ? '200K' : '500K' } },
    { key: `${limitLabel}-director-info`, type: 'api', method: 'POST', kind: '自定义请求', title: '邓白氏提交法人信息', endpoint: '/api/mock/fp-director-info', operationKey: null, payload: { journey: limitLabel === '2K' ? '200K' : '500K' } },
    { key: `${limitLabel}-offer-select`, type: 'api', method: 'POST', kind: '自定义请求', title: offerName, endpoint: '/api/mock/fp-offer-limit-select', operationKey: null, payload: { journey: limitLabel === '2K' ? '200K' : '500K' } },
    { key: `${limitLabel}-offer-quote`, type: 'api', method: 'POST', kind: '自定义请求', title: '激活offer额度报价', endpoint: '/api/mock/fp-offer-quote-activate', operationKey: null, payload: { journey: limitLabel === '2K' ? '200K' : '500K' } },
    { key: `${limitLabel}-associate`, type: 'api', method: 'POST', kind: '自定义请求', title: '关联SP和3PL店铺', endpoint: '/api/mock/fp-link-sp-3pl-shops', operationKey: null, payload: { journey: limitLabel === '2K' ? '200K' : '500K' } },
    { key: `${limitLabel}-scheduled`, type: 'api', method: 'POST', kind: '自定义请求', title: 'run-fp-scheduled-tasks-and-poll-submitted', endpoint: '/api/mock/fp-scheduled-submit', operationKey: null, payload: { journey: limitLabel === '2K' ? '200K' : '500K' } },
    { key: `${limitLabel}-underwritten`, type: 'api', method: 'POST', kind: '自定义请求', title: 'underwritten', endpoint: '/api/mock/underwritten', operationKey: 'underwritten' },
    { key: `${limitLabel}-approved-offer`, type: 'api', method: 'POST', kind: '自定义请求', title: 'approved-offer', endpoint: '/api/mock/approved-offer', operationKey: 'approvedOffer' },
    { key: `${limitLabel}-psp-start`, type: 'api', method: 'POST', kind: '自定义请求', title: 'psp-start', endpoint: '/api/mock/psp-start', operationKey: 'pspStart' },
    { key: `${limitLabel}-psp-completed`, type: 'api', method: 'POST', kind: '自定义请求', title: 'psp-completed', endpoint: '/api/mock/psp-completed', operationKey: 'pspCompleted' },
    { key: `${limitLabel}-esign`, type: 'api', method: 'POST', kind: '自定义请求', title: 'esign', endpoint: '/api/mock/esign', operationKey: 'esign' },
  ]
}

function buildDsCnyScenarioSteps() {
  const flowEndpoint = 'flow: register-and-run-multishop'
  return [
    { key: 'DS-CNY-sms', type: 'flow', method: 'FLOW', kind: '场景步骤', title: '发送注册短信', endpoint: flowEndpoint },
    { key: 'DS-CNY-token', type: 'flow', method: 'FLOW', kind: '场景步骤', title: '验证码调用验证生成一次token', endpoint: flowEndpoint },
    { key: 'DS-CNY-signup', type: 'flow', method: 'FLOW', kind: '场景步骤', title: '用户注册', endpoint: flowEndpoint },
    { key: 'DS-CNY-state', type: 'flow', method: 'FLOW', kind: '场景步骤', title: '生成state做sp', endpoint: flowEndpoint },
    { key: 'DS-CNY-sp-auth', type: 'flow', method: 'FLOW', kind: '场景步骤', title: '进行SP授权', endpoint: flowEndpoint },
    { key: 'DS-CNY-update-offer', type: 'flow', method: 'FLOW', kind: '场景步骤', title: 'sp-updateOffer(成功)', endpoint: flowEndpoint },
    { key: 'DS-CNY-3pl-auth', type: 'flow', method: 'FLOW', kind: '场景步骤', title: '亚马逊3PL授权', endpoint: flowEndpoint },
    { key: 'DS-CNY-3pl-auth-result', type: 'flow', method: 'FLOW', kind: '场景步骤', title: '3PL AUTH授权', endpoint: flowEndpoint },
    {
      key: 'DS-CNY-shop-performance-sql',
      type: 'api',
      method: 'POST',
      kind: 'SQL步骤',
      title: '更新3PL店铺经营数据',
      endpoint: '/api/mock/shop-performance-cny-boost',
      operationKey: null,
      payload: {
        offer_id: '${platform_offer_id}',
      },
    },
    {
      key: 'DS-CNY-application',
      type: 'api',
      method: 'POST',
      kind: '自定义请求',
      title: '创建 DOWSURE 申请单',
      endpoint: '/api/mock/create-application-context',
      operationKey: null,
      payload: {
        journey: '500K',
        currency: 'CNY',
        funder_resource: 'DOWSURE',
        offer_id: '${platform_offer_id}',
        tier_code: 4,
      },
    },
    {
      key: 'DS-CNY-business-info',
      type: 'api',
      method: 'POST',
      kind: '自定义请求',
      title: '邓白氏提交企业信息',
      endpoint: '/api/mock/fp-business-profile',
      operationKey: null,
      payload: {
        journey: '500K',
        currency: 'CNY',
        funder_resource: 'DOWSURE',
      },
    },
    {
      key: 'DS-CNY-director-info',
      type: 'api',
      method: 'POST',
      kind: '自定义请求',
      title: '邓白氏提交法人信息',
      endpoint: '/api/mock/fp-director-info',
      operationKey: null,
      payload: {
        journey: '500K',
        currency: 'CNY',
        funder_resource: 'DOWSURE',
        nameCn: '巨鹏',
        addressDetail: '广州市天河区测试路1号',
      },
    },
    {
      key: 'DS-CNY-start-reassessment',
      type: 'api',
      method: 'POST',
      kind: '自定义请求',
      title: '开始信用评估',
      endpoint: '/api/mock/fp-start-reassessment',
      operationKey: null,
      payload: {
        journey: '500K',
        currency: 'CNY',
        funder_resource: 'DOWSURE',
      },
    },
  ]
}

const aiQuickPrompts = [
  '帮我看一下当前 session 的状态，哪些关键信息还缺失？',
  '查询当前手机号对应的 merchant_id',
  '根据最近日志分析失败原因，并告诉我下一步怎么查',
  'SELECT merchant_id, phone_number FROM dpu_users ORDER BY created_at DESC LIMIT 5',
]

watch(applicationOptions, (applications) => {
  if (!applications.length) {
    selectedApplicationUniqueId.value = ''
    return
  }
  if (!selectedApplicationUniqueId.value || !applications.some((item) => item.application_unique_id === selectedApplicationUniqueId.value)) {
    selectedApplicationUniqueId.value = (
      sessionSummary.value?.selected_application_unique_id
      || sessionSummary.value?.application_unique_id
      || applications[0].application_unique_id
      || ''
    )
  }
})

watch(
  () => connectionForm.env,
  (value) => {
    registerForm.env = value
  },
)

watch(
  [activeOperationKey, activeSessionId],
  () => {
    if (shouldShowDowsureMerchantAccounts.value) {
      loadDowsureMerchantAccounts()
    } else {
      dowsureMerchantAccounts.value = []
      operationForms.underwrittenDowsure.merchant_accounts = []
    }
    if (shouldShowPspAuthorizationRows.value) {
      loadPspAuthorizationRows()
    } else {
      selectedPspMerchantAccountId.value = ''
      pspSelectionTouched.value = false
    }
  },
)

watch(
  operations,
  (items) => {
    interfaceScenarios.value.flatMap((scenario) => scenario.steps).forEach((item) => {
      if (interfaceStepEnabled[item.key] === undefined) interfaceStepEnabled[item.key] = true
    })
    if (!activeOperationKey.value && activeInterfaceScenario.value.steps.length > 0) {
      activeOperationKey.value = activeInterfaceScenario.value.steps[0].key
    }
  },
  { immediate: true },
)

watch(activeInterfaceScenarioKey, () => {
  activeOperationKey.value = activeInterfaceScenario.value.steps[0]?.key || ''
  if (activeInterfaceScenario.value.bootstrap?.env) {
    connectionForm.env = activeInterfaceScenario.value.bootstrap.env
    registerForm.env = activeInterfaceScenario.value.bootstrap.env
  }
})

watch(darkMode, (value) => {
  document.documentElement.classList.toggle('mockapi-dark', value)
  window.localStorage.setItem('mockapi-theme', value ? 'dark' : 'light')
}, { immediate: true })

watch(scenarioExecutionHistory, persistScenarioExecutionHistory, { deep: true })

onMounted(async () => {
  const savedTheme = window.localStorage.getItem('mockapi-theme')
  if (savedTheme) {
    darkMode.value = savedTheme === 'dark'
  } else {
    darkMode.value = window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
  }
  restoreScenarioExecutionHistory()
  restoreAuthUser()
  loadContactIssues()
  await Promise.all([refreshHealth(), loadEnums(), loadSessions()])
})

onBeforeUnmount(() => {
  closeSocket()
  stopSessionPolling()
})

async function refreshHealth() {
  loadingHealth.value = true
  try {
    await fetchHealth()
    health.value = 'ok'
  } catch (error) {
    health.value = normalizeError(error)
  } finally {
    loadingHealth.value = false
  }
}

async function loadEnums() {
  loadingEnums.value = true
  try {
    enumOptions.value = await fetchEnums()
  } catch (error) {
    pushActivity('error', '加载枚举失败', normalizeError(error))
  } finally {
    loadingEnums.value = false
  }
}

async function loadSessions() {
  loadingSessions.value = true
  try {
    if (!activeSessionId.value) {
      liveSessions.value = []
      return
    }
    liveSessions.value = await fetchSessions(activeSessionId.value)
  } catch (error) {
    pushActivity('error', '刷新会话列表失败', normalizeError(error))
  } finally {
    loadingSessions.value = false
  }
}

async function refreshSessionsQuietly() {
  if (!activeSessionId.value) return
  try {
    liveSessions.value = await fetchSessions(activeSessionId.value)
  } catch (error) {
    pushActivity('error', '轮询刷新会话失败', normalizeError(error))
  }
}

function startSessionPolling() {
  stopSessionPolling()
  sessionPollTimer = window.setInterval(refreshSessionsQuietly, 5000)
}

function stopSessionPolling() {
  if (!sessionPollTimer) return
  window.clearInterval(sessionPollTimer)
  sessionPollTimer = null
}

async function loadPspAuthorizationRows() {
  if (!activeSessionId.value) {
    pspAuthorizationRows.value = []
    selectedPspMerchantAccountId.value = ''
    pspSelectionTouched.value = false
    return
  }
  loadingPspAuthorizationRows.value = true
  try {
    const result = await fetchPspAuthorizationRows(activeSessionId.value)
    pspAuthorizationRows.value = result.rows ?? []
    const currentSelectionStillValid = pspAuthorizationRows.value.some(
      (row) => row.merchant_account_id === selectedPspMerchantAccountId.value && isPspRowSelectable(row),
    )
    if (pspSelectionTouched.value) {
      if (!currentSelectionStillValid) {
        selectedPspMerchantAccountId.value = ''
        pspSelectionTouched.value = false
      }
    } else {
      const defaultMerchantAccountId = result.default_selected_merchant_account_id
      const defaultRow = pspAuthorizationRows.value.find(
        (row) => row.merchant_account_id === defaultMerchantAccountId && isPspRowSelectable(row),
      )
      selectedPspMerchantAccountId.value = defaultRow?.merchant_account_id || ''
    }
    if (!pspAuthorizationRows.value.some((row) => row.merchant_account_id === selectedPspMerchantAccountId.value && isPspRowSelectable(row))) {
      selectedPspMerchantAccountId.value = ''
    }
  } catch (error) {
    pspAuthorizationRows.value = []
    selectedPspMerchantAccountId.value = ''
    pspSelectionTouched.value = false
    pushActivity('error', '加载 PSP 授权状态失败', normalizeError(error))
  } finally {
    loadingPspAuthorizationRows.value = false
  }
}

async function loadDowsureMerchantAccounts() {
  if (!activeSessionId.value) {
    dowsureMerchantAccounts.value = []
    operationForms.underwrittenDowsure.merchant_accounts = []
    return
  }
  loadingDowsureMerchantAccounts.value = true
  try {
    const result = await fetchDowsureMerchantAccounts(activeSessionId.value)
    dowsureMerchantAccounts.value = result.accounts ?? []
    operationForms.underwrittenDowsure.merchant_accounts = dowsureMerchantAccounts.value.map((item) => ({
      merchantAccountId: item.merchantAccountId,
      merchantAccountLimit: item.merchantAccountLimit ?? null,
      merchant_account_id: item.merchant_account_id ?? '',
      created_at: item.created_at ?? '',
    }))
  } catch (error) {
    dowsureMerchantAccounts.value = []
    operationForms.underwrittenDowsure.merchant_accounts = []
    pushActivity('error', '加载 DOWSURE 店铺失败', normalizeError(error))
  } finally {
    loadingDowsureMerchantAccounts.value = false
  }
}

async function handleConnect() {
  connecting.value = true
  try {
    await establishSession({ ...connectionForm }, '会话连接成功')
  } catch (error) {
    const message = normalizeError(error)
    ElMessage.error(message === 'PHONE_NOT_FOUND' ? '该手机号不存在' : message)
    pushActivity('error', '会话连接失败', message === 'PHONE_NOT_FOUND' ? '该手机号不存在' : message)
  } finally {
    connecting.value = false
  }
}

async function handleDisconnect() {
  if (!activeSessionId.value) return
  const sessionId = activeSessionId.value
  disconnecting.value = true
  try {
    await disconnectSession(sessionId)
    pushActivity('disconnect', '会话已断开', { session_id: sessionId })
    closeSocket()
    stopSessionPolling()
    activeSessionId.value = ''
    await loadSessions()
  } catch (error) {
    pushActivity('error', '断开会话失败', normalizeError(error))
  } finally {
    disconnecting.value = false
  }
}

async function handleRegister() {
  registering.value = true
  try {
    registerAutoConnected.value = false
    registerResult.value = await registerAccount({ ...registerForm, username: authUser.value?.username })
    showRegisterToast('success', '注册成功')
    pushActivity('register', '注册完成', registerResult.value)

    if (registerResult.value?.phone_number) {
      connectionForm.env = registerForm.env
      connectionForm.phone_number = registerResult.value.phone_number
      try {
        await connectAfterRegister(registerResult.value.phone_number, registerForm.env)
        registerAutoConnected.value = true
      } catch (error) {
        pushActivity('error', '注册后自动连接失败', `${normalizeError(error)}。你也可以直接点击“连接 session”重试。`)
        registerAutoConnected.value = false
      }
    }
  } catch (error) {
    registerAutoConnected.value = false
    showRegisterToast('error', `注册失败：${normalizeError(error)}`)
    pushActivity('error', '注册失败', normalizeError(error))
  } finally {
    registering.value = false
  }
}

async function handleRegisterAndRunMultiShop() {
  registeringAndBinding.value = true
  try {
    registerAutoConnected.value = false
    const payload = {
      ...registerForm,
      sp_status: 'SUCCESS',
      username: authUser.value?.username,
    }
    registerResult.value = await registerAndRunMultiShop(payload)
    showRegisterToast('success', '注册成功')
    pushActivity('register', '注册并完成绑店完成', registerResult.value)

    const session = registerResult.value?.session
    const phoneNumber = session?.phone_number || registerResult.value?.register_result?.phone_number
    if (phoneNumber) {
      connectionForm.env = payload.env
      connectionForm.phone_number = phoneNumber
      try {
        await connectAfterRegister(phoneNumber, payload.env)
        registerAutoConnected.value = true
      } catch (error) {
        pushActivity('error', '注册并完成绑店后自动连接失败', `${normalizeError(error)}。你也可以直接点击“连接 session”重试。`)
      }
    }
  } catch (error) {
    registerAutoConnected.value = false
    showRegisterToast('error', `注册失败：${normalizeError(error)}`)
    pushActivity('error', '注册并完成绑店失败', normalizeError(error))
  } finally {
    registeringAndBinding.value = false
  }
}

async function handleOperationRun(operation, payloadOverrides = {}) {
  if (!activeSessionId.value) {
    pushActivity('error', '请先连接会话', '当前没有 session_id，无法执行 mock 操作。')
    return null
  }

  runningOperationKey.value = operation.key
  const requestPayload = { ...buildPayload(operation), ...payloadOverrides }
  const requestDetail = {
    method: 'POST',
    endpoint: operation.endpoint,
    body: requestPayload,
  }
  try {
    const data = await runMockOperation(operation.endpoint, requestPayload)
    const successResult = buildOperationResult('success', data)
    operationResults[operation.key] = successResult
    syncDowsureFollowupFields(operation.key, data)
    showOperationToast('success', `${operation.title} 执行成功`, data)
    pushActivity('mock', `${operation.title} 已执行`, data)
    if (['pspStart', 'pspCompleted'].includes(operation.key)) {
      await loadPspAuthorizationRows()
    }
    return { request: requestDetail, response: successResult, error: false }
  } catch (error) {
    const failureResult = buildOperationResult('error', getErrorPayload(error), normalizeError(error))
    operationResults[operation.key] = failureResult
    showOperationToast('error', `${operation.title} 执行失败`, failureResult)
    pushActivity('error', `${operation.title} 执行失败`, failureResult)
    return { request: requestDetail, response: failureResult, error: true }
  } finally {
    runningOperationKey.value = ''
  }
}

async function handleScenarioStepRun(step) {
  if (step.endpoint === 'flow: register-and-run-multishop') {
    const bootstrapResult = await bootstrapScenarioSession()
    latestScenarioRunContext.value = {
      env: connectionForm.env,
      phone_number: bootstrapResult.session?.phone_number || bootstrapResult.register?.register_result?.phone_number || '',
      merchant_id: bootstrapResult.session?.merchant_id || '',
      application_unique_id: bootstrapResult.session?.application_unique_id || '',
    }
    const platformOfferId = extractPlatformOfferId(bootstrapResult)
    if (platformOfferId) {
      scenarioVariables.platform_offer_id = platformOfferId
    }
    const bootstrapKeys = interfaceAutomationSteps.value
      .filter((item) => item.endpoint === 'flow: register-and-run-multishop')
      .map((item) => item.key)
    bootstrapKeys.forEach((key) => {
      scenarioStepResults[key] = {
        status: 'success',
        at: new Date().toLocaleTimeString(),
        request: {
          method: 'POST',
          endpoint: '/api/register-and-run-multishop',
          body: getScenarioBootstrapPayload(),
        },
        response: bootstrapResult,
        payload: bootstrapResult,
      }
    })
    pushActivity('scenario', '线下注册并完成绑店完成', {
      scenario: activeInterfaceScenario.value.name,
      session_id: bootstrapResult.session?.session_id,
      phone_number: bootstrapResult.session?.phone_number,
    })
    return
  }
  if (!step.operation && step.endpoint.startsWith('/api/')) {
    const payload = buildScenarioApiPayload(step)
    try {
      const data = await runScenarioApi(step.endpoint, payload, {
        timeout: getScenarioStepTimeout(step),
      })
      scenarioStepResults[step.key] = {
        status: 'success',
        at: new Date().toLocaleTimeString(),
        request: { method: step.method || 'POST', endpoint: step.endpoint, body: payload },
        response: data,
        payload: data,
      }
      latestScenarioRunContext.value = {
        env: connectionForm.env,
        phone_number: latestScenarioRunContext.value?.phone_number || sessionSummary.value?.phone_number || connectionForm.phone_number || '',
        merchant_id: data?.merchant_id || latestScenarioRunContext.value?.merchant_id || sessionSummary.value?.merchant_id || '',
        application_unique_id: data?.application_unique_id || latestScenarioRunContext.value?.application_unique_id || '',
      }
      if (data?.application_unique_id) {
        scenarioVariables.application_unique_id = data.application_unique_id
      }
      if (data?.limit_application_unique_id) {
        scenarioVariables.limit_application_unique_id = data.limit_application_unique_id
      }
      if (data?.lender_approved_offer_id) {
        scenarioVariables.lender_approved_offer_id = data.lender_approved_offer_id
      }
      const platformOfferId = extractPlatformOfferId(data)
      if (platformOfferId) {
        scenarioVariables.platform_offer_id = platformOfferId
      }
      pushActivity('scenario', `${step.title} 已执行`, data)
    } catch (error) {
      const failure = buildOperationResult('error', getErrorPayload(error), normalizeError(error))
      scenarioStepResults[step.key] = {
        status: 'error',
        at: new Date().toLocaleTimeString(),
        request: { method: step.method || 'POST', endpoint: step.endpoint, body: payload },
        response: failure,
        payload: failure,
      }
      pushActivity('error', `${step.title} 执行失败`, failure)
    }
    return
  }
  if (!step.operation) {
    const placeholder = { message: '该步骤是场景编排节点，暂未绑定单步 mock 接口。' }
    scenarioStepResults[step.key] = {
      status: 'idle',
      at: new Date().toLocaleTimeString(),
      request: { method: step.method || 'FLOW', endpoint: step.endpoint, body: step.payload || null },
      response: placeholder,
      payload: placeholder,
    }
    pushActivity('scenario', `${step.title} 是场景编排步骤，暂未绑定单步 mock 接口`, {
      scenario: activeInterfaceScenario.value.name,
      step: step.title,
      endpoint: step.endpoint,
    })
    return
  }
  activeOperationKey.value = step.key
  const result = await handleOperationRun(step.operation, {
    operation_name: getScenarioOperationName(step),
  })
  if (result) {
    scenarioStepResults[step.key] = {
      status: result.error ? 'error' : 'success',
      at: new Date().toLocaleTimeString(),
      request: result.request,
      response: result.response,
      payload: result.response,
    }
  }
}

function markScenarioStep(step, status, payload = null) {
  scenarioStepResults[step.key] = {
    status,
    at: new Date().toLocaleTimeString(),
    request: getScenarioStepRequest(step),
    response: payload,
    payload,
  }
}

function getScenarioJourney(scenario = activeInterfaceScenario.value) {
  return scenario.key === 'fpUsd2k' ? '200K' : '500K'
}

function getScenarioBootstrapConfig(scenario = activeInterfaceScenario.value) {
  return {
    currency: scenario.bootstrap?.currency || 'USD',
    funder_resource: scenario.bootstrap?.funder_resource || 'FUNDPARK',
    offline: scenario.bootstrap?.offline ?? true,
    sp_status: scenario.bootstrap?.sp_status || 'SUCCESS',
  }
}

async function bootstrapScenarioSession() {
  const env = connectionForm.env || registerForm.env || activeInterfaceScenario.value.bootstrap?.env || 'reg'
  const journey = getScenarioJourney()
  const payload = getScenarioBootstrapPayload(env, journey)
  const bootstrapConfig = getScenarioBootstrapConfig()
  registerForm.env = env
  registerForm.journey = journey
  registerForm.currency = bootstrapConfig.currency
  registerForm.funder_resource = bootstrapConfig.funder_resource
  registerForm.offline = bootstrapConfig.offline
  registerResult.value = await registerAndRunMultiShop(payload)
  const phoneNumber = registerResult.value?.session?.phone_number || registerResult.value?.register_result?.phone_number
  if (!phoneNumber) {
    throw new Error('线下注册并完成绑店成功但没有返回 phone_number')
  }
  connectionForm.env = env
  connectionForm.phone_number = phoneNumber
  const existingSession = registerResult.value?.session
  let session = existingSession
  if (existingSession?.session_id) {
    activeSessionId.value = existingSession.session_id
    selectedApplicationUniqueId.value = (
      existingSession.selected_application_unique_id
      || existingSession.application_unique_id
      || existingSession.applications?.[0]?.application_unique_id
      || ''
    )
    pushActivity('connect', '复用绑店流程返回会话', existingSession)
    await loadSessions()
    connectLogs(existingSession.session_id)
    startSessionPolling()
  } else {
    session = await connectAfterRegister(phoneNumber, env)
  }
  await loadSessions()
  registerAutoConnected.value = true
  return { register: registerResult.value, session }
}

function getScenarioBootstrapPayload(env = connectionForm.env || registerForm.env || activeInterfaceScenario.value.bootstrap?.env || 'reg', journey = getScenarioJourney()) {
  const bootstrapConfig = getScenarioBootstrapConfig()
  return {
    env,
    journey,
    currency: bootstrapConfig.currency,
    funder_resource: bootstrapConfig.funder_resource,
    offline: bootstrapConfig.offline,
    sp_status: bootstrapConfig.sp_status,
    username: authUser.value?.username,
    operation_name: `${activeInterfaceScenario.value.name}.register-and-run-multishop`,
  }
}

function buildScenarioApiPayload(step) {
  return {
    session_id: activeSessionId.value,
    username: authUser.value?.username,
    operation_name: getScenarioOperationName(step),
    ...resolveScenarioPayload(step.payload || {}),
  }
}

function getScenarioOperationName(step, scenario = activeInterfaceScenario.value) {
  return `${scenario.name}.${step.key}`
}

function resolveScenarioPayload(payload) {
  if (Array.isArray(payload)) {
    return payload.map((item) => resolveScenarioPayload(item))
  }
  if (payload && typeof payload === 'object') {
    return Object.fromEntries(
      Object.entries(payload).map(([key, value]) => [key, resolveScenarioPayload(value)]),
    )
  }
  if (typeof payload !== 'string') return payload
  const match = payload.match(/^\$\{([a-zA-Z0-9_]+)\}$/)
  if (!match) return payload
  const resolved = scenarioVariables[match[1]]
  if (!resolved || resolved === payload) return ''
  return resolved
}

function getScenarioStepTimeout(step) {
  if (step.endpoint === '/api/mock/fp-scheduled-submit') return 780000
  return undefined
}

function resetScenarioRuntimeVariables() {
  scenarioVariables.phone_number = '${phone_number}'
  scenarioVariables.session_id = '${session_id}'
  scenarioVariables.merchant_id = '${merchant_id}'
  scenarioVariables.platform_offer_id = '${platform_offer_id}'
  scenarioVariables.application_unique_id = '${application_unique_id}'
  scenarioVariables.limit_application_unique_id = '${limit_application_unique_id}'
  scenarioVariables.lender_approved_offer_id = '${lender_approved_offer_id}'
}

function extractPlatformOfferId(payload) {
  if (!payload || typeof payload !== 'object') return ''
  const roots = [payload.result, payload.data, payload].filter(Boolean)
  for (const root of roots) {
    const stepOfferId = extractPlatformOfferIdFromSteps(root.steps)
    if (stepOfferId) return stepOfferId
    const direct = getValidPlatformOfferId(
      root.platform_offer_id
      || root.offer_id
      || root.register_result?.offer_id
      || root.redirect_post?.payload?.offerId
      || root.request_info?.body?.offerId,
    )
    if (direct) return direct
  }
  return ''
}

function extractPlatformOfferIdFromSteps(steps) {
  if (!Array.isArray(steps)) return ''
  const reversedSteps = [...steps].reverse()
  const preferredSteps = reversedSteps.filter((item) => (
    String(item?.step || '').includes('3PL')
    || String(item?.step || '').includes('manual offer')
    || item?.endpoint === 'dpu_manual_offer'
  ))
  for (const step of [...preferredSteps, ...reversedSteps]) {
    const candidates = [
      step?.result?.platform_offer_id,
      step?.result?.redirect_post?.payload?.offerId,
      step?.result?.request_info?.body?.offerId,
      step?.response?.platform_offer_id,
      step?.response?.body?.platform_offer_id,
      step?.response?.body?.offerId,
      step?.payload?.offerId,
    ]
    const offerId = candidates.map(getValidPlatformOfferId).find(Boolean)
    if (offerId) return offerId
  }
  return ''
}

function getValidPlatformOfferId(value) {
  const offerId = String(value || '').trim()
  if (!offerId || offerId.startsWith('${')) return ''
  if (!offerId.includes('TESTOFFER')) return ''
  return offerId
}

function getScenarioStepRequest(step) {
  if (!step) return null
  if (step.endpoint === 'flow: register-and-run-multishop') {
    return { method: 'POST', endpoint: '/api/register-and-run-multishop', body: getScenarioBootstrapPayload() }
  }
  if (!step.operation && step.endpoint.startsWith('/api/')) {
    return { method: step.method || 'POST', endpoint: step.endpoint, body: buildScenarioApiPayload(step) }
  }
  if (step.operation) {
    return { method: 'POST', endpoint: step.operation.endpoint, body: buildPayload(step.operation) }
  }
  return { method: step.method || 'FLOW', endpoint: step.endpoint, body: step.payload || null }
}

function getScenarioStepRequestBody(step) {
  const body = scenarioStepResults[step.key]?.request?.body ?? getScenarioStepRequest(step)?.body ?? null
  if (body?.request_info?.body) return body.request_info.body
  if (body?.body && body?.method && body?.url) return body.body
  return body
}

function getScenarioStepResponse(step) {
  return normalizeScenarioStepResponse(scenarioStepResults[step.key]?.response ?? scenarioStepResults[step.key]?.payload ?? null)
}

function parseMaybeJson(value) {
  if (!value || typeof value !== 'string') return null
  try {
    return JSON.parse(value)
  } catch {
    return null
  }
}

function pickTraceId(payload, body) {
  return (
    body?.traceId
    || payload?.traceId
    || payload?.response_info?.headers?.traceId
    || payload?.response_info?.headers?.['X-Trace-Id']
    || payload?.response_headers?.traceId
    || payload?.response_headers?.['X-Trace-Id']
    || null
  )
}

function getResponseBody(payload) {
  if (!payload || typeof payload !== 'object') return payload
  return (
    payload.response_json
    || payload.response_info?.json
    || parseMaybeJson(payload.response_body)
    || parseMaybeJson(payload.response_info?.body)
    || parseMaybeJson(payload.response)
    || payload.data
    || payload
  )
}

function normalizeNestedStepResult(step) {
  const request = step.payload ?? step.request ?? step.request_body ?? null
  const responsePayload = step.result ?? step.response ?? null
  return {
    step: step.step || step.name || step.title || null,
    endpoint: step.endpoint || step.url || null,
    request,
    response: normalizeScenarioStepResponse(responsePayload),
  }
}

function normalizeScenarioStepResponse(payload) {
  if (!payload) return null
  if (typeof payload !== 'object') return payload

  const body = getResponseBody(payload)

  if (body && typeof body === 'object' && Array.isArray(body.steps)) {
    const normalizedBody = {
      success: body.success ?? payload.success ?? null,
      application_unique_id: body.application_unique_id ?? payload.application_unique_id ?? null,
      steps: body.steps.map(normalizeNestedStepResult),
    }
    return {
      success: payload.success ?? body.success ?? body.isSuccess ?? null,
      status_code: payload.status_code ?? payload.response_info?.status_code ?? body.code ?? null,
      traceId: pickTraceId(payload, body),
      body: normalizedBody,
    }
  }

  const normalized = {
    success: payload.success ?? body?.success ?? body?.isSuccess ?? null,
    status_code: payload.status_code ?? payload.response_info?.status_code ?? body?.code ?? null,
    traceId: pickTraceId(payload, body),
    body,
  }

  if (payload.error_message) normalized.error_message = payload.error_message
  return normalized
}

function getScenarioStepDetailTab(step) {
  return scenarioStepDetailTabs[step.key] || 'params'
}

function setScenarioStepDetailTab(step, tab) {
  scenarioStepDetailTabs[step.key] = tab
}

function getScenarioStepDescription(step) {
  const request = getScenarioStepRequest(step)
  const fields = step.operation?.fields || []
  return {
    title: step.title,
    kind: step.kind,
    method: request?.method || step.method || 'FLOW',
    endpoint: request?.endpoint || step.endpoint,
    description: step.operation?.description || (
      step.type === 'flow'
        ? `${step.title} 由场景执行器统一驱动，执行服务端流程后会回填该节点结果。`
        : `${step.title} 是当前场景中的接口编排步骤。`
    ),
    fieldCount: fields.length,
    fields: fields.map((field) => ({
      label: field.label,
      prop: field.prop,
      type: field.type || 'text',
    })),
  }
}

function getScenarioResponseState(step) {
  const status = scenarioStepResults[step.key]?.status
  if (status === 'error') return { type: 'danger', label: 'Error' }
  if (status === 'success') return { type: 'success', label: 'Latest' }
  return { type: 'info', label: 'Empty' }
}

function hasScenarioStepDetail(step) {
  return Boolean(expandedScenarioSteps[step.key] || selectedInterfaceStep.value?.key === step.key || scenarioStepResults[step.key])
}

function toggleScenarioStep(step) {
  activeOperationKey.value = step.key
  expandedScenarioSteps[step.key] = !expandedScenarioSteps[step.key]
}

function restoreScenarioExecutionHistory() {
  try {
    const raw = window.localStorage.getItem(scenarioHistoryStorageKey)
    if (!raw) return
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed)) {
      scenarioExecutionHistory.value = parsed
    }
  } catch (error) {
    window.localStorage.removeItem(scenarioHistoryStorageKey)
  }
}

function persistScenarioExecutionHistory() {
  try {
    window.localStorage.setItem(scenarioHistoryStorageKey, JSON.stringify(scenarioExecutionHistory.value))
  } catch (error) {
    pushActivity('error', '执行历史保存失败', normalizeError(error))
  }
}

function cloneScenarioPayload(payload) {
  if (payload === undefined) return null
  try {
    return JSON.parse(JSON.stringify(payload))
  } catch (error) {
    return String(payload)
  }
}

function buildScenarioStepSnapshot(step, fallbackStatus = 'idle') {
  const result = scenarioStepResults[step.key]
  return {
    key: step.key,
    order: step.order,
    title: step.title,
    kind: step.kind,
    method: result?.request?.method || step.method || 'POST',
    endpoint: result?.request?.endpoint || step.endpoint,
    status: result?.status || fallbackStatus,
    at: result?.at || null,
    request: cloneScenarioPayload(result?.request ?? getScenarioStepRequest(step)),
    response: cloneScenarioPayload(result?.response ?? result?.payload ?? null),
    error_message: result?.response?.error_message || result?.payload?.error_message || result?.response?.message || null,
  }
}

function buildScenarioRunStepSnapshots(enabledSteps) {
  return enabledSteps.map((step) => buildScenarioStepSnapshot(step, step.enabled === false ? 'skipped' : 'idle'))
}

function addScenarioExecutionRecord(record) {
  scenarioExecutionHistory.value = [record, ...scenarioExecutionHistory.value]
}

function openScenarioHistoryDetail(record) {
  selectedScenarioHistoryRecord.value = record
  scenarioHistoryDetailVisible.value = true
}

function getScenarioBootstrapKeys() {
  return interfaceAutomationSteps.value
    .filter((item) => [
      'flow: register-and-run-multishop',
      'flow: create-application-from-session',
      'flow: offer-limit-selected',
      'flow: linked-during-bootstrap',
      'flow: offer-quote-confirmed',
    ].includes(item.endpoint))
    .map((item) => item.key)
}

function getScenarioPostBootstrapFlowKeys() {
  return interfaceAutomationSteps.value
    .filter((item) => ['underwritten', 'approvedOffer', 'pspStart', 'pspCompleted', 'esign'].includes(item.operationKey))
    .map((item) => item.key)
}

function handleScenarioSave() {
  scenarioSaveState.value = '保存中'
  window.setTimeout(() => {
    scenarioSaveState.value = `已保存 ${new Date().toLocaleTimeString()}`
    pushActivity('scenario', `${activeInterfaceScenario.value.name} 已保存`, {
      scenario: activeInterfaceScenario.value.name,
      enabled_steps: enabledInterfaceStepCount.value,
    })
    ElMessage.success('场景已保存')
  }, 350)
}

function handleScenarioCreate() {
  activeInterfaceScenarioKey.value = 'fpUsd2k'
  activeScenarioTab.value = 'base'
  scenarioSaveState.value = '未保存'
  ElMessage.success('已创建 FP-USD-2K 场景草稿')
  pushActivity('scenario', '新建场景草稿', { scenario: 'FP-USD-2K' })
}

function handleScenarioImport() {
  activeInterfaceScenarioKey.value = 'fpUsd500k'
  activeScenarioTab.value = 'steps'
  ElMessage.success('已导入 FP-USD-500K 场景模板')
  pushActivity('scenario', '导入场景模板', { scenario: 'FP-USD-500K', steps: 18 })
}

function handleScenarioAddStep() {
  activeScenarioTab.value = 'steps'
  ElMessage.info('当前场景步骤来自 MeterSphere 模板，新增步骤请先在模板中维护。')
  pushActivity('scenario', '点击添加步骤', { scenario: activeInterfaceScenario.value.name })
}

async function handleScenarioServerExecute() {
  if (scenarioExecuting.value) return
  if (scenarioSettings.validateSession && !activeSessionId.value) {
    const record = {
      id: `${Date.now()}`,
      scenario: activeInterfaceScenario.value.name,
      env: connectionForm.env,
      at: new Date().toLocaleString(),
      duration: '0s',
      success: 0,
      skipped: 0,
      failed: enabledInterfaceStepCount.value,
      status: '未执行',
      context: cloneScenarioPayload(latestScenarioRunContext.value),
      steps: buildScenarioRunStepSnapshots(interfaceAutomationSteps.value.filter((step) => step.enabled)),
    }
    addScenarioExecutionRecord(record)
    ElMessage.warning('执行前校验失败：请先连接 session')
    pushActivity('scenario', `${record.scenario} 执行前校验失败`, record)
    activeScenarioTab.value = 'history'
    return
  }
  scenarioExecuting.value = true
  try {
    latestScenarioRunContext.value = null
    resetScenarioRuntimeVariables()
    const startedAt = new Date()
    const enabledSteps = interfaceAutomationSteps.value.filter((step) => step.enabled)
    let successCount = 0
    let skippedCount = 0
    let failCount = 0
    let bootstrapDone = false

    for (const step of enabledSteps) {
      if (step.endpoint === 'flow: register-and-run-multishop') {
        if (!bootstrapDone) {
          try {
            const bootstrapResult = await bootstrapScenarioSession()
            getScenarioBootstrapKeys().forEach((key) => {
              scenarioStepResults[key] = {
                status: 'success',
                at: new Date().toLocaleTimeString(),
                request: {
                  method: 'POST',
                  endpoint: '/api/register-and-run-multishop',
                  body: getScenarioBootstrapPayload(),
                },
                response: bootstrapResult,
                payload: bootstrapResult,
              }
            })
            const bootstrapCount = interfaceAutomationSteps.value
              .filter((item) => (
                item.enabled
                && item.endpoint === 'flow: register-and-run-multishop'
              ))
              .length
            successCount += bootstrapCount
            bootstrapDone = true
            const platformOfferId = extractPlatformOfferId(bootstrapResult)
            if (platformOfferId) {
              scenarioVariables.platform_offer_id = platformOfferId
            }
            pushActivity('scenario', '线下注册并完成绑店完成', {
              scenario: activeInterfaceScenario.value.name,
              session_id: bootstrapResult.session?.session_id,
              phone_number: bootstrapResult.session?.phone_number,
            })
          } catch (error) {
            getScenarioBootstrapKeys().forEach((key) => {
              const failure = buildOperationResult('error', getErrorPayload(error), normalizeError(error))
              scenarioStepResults[key] = {
                status: 'error',
                at: new Date().toLocaleTimeString(),
                request: {
                  method: 'POST',
                  endpoint: '/api/register-and-run-multishop',
                  body: getScenarioBootstrapPayload(),
                },
                response: failure,
                payload: failure,
              }
            })
            failCount += 1
            if (scenarioSettings.stopOnFailure) break
          }
        }
        continue
      }
      if (!step.operation && !step.endpoint.startsWith('/api/')) {
        skippedCount += 1
        markScenarioStep(step, 'skipped', { message: '该步骤未绑定可执行接口。' })
        continue
      }
      if (!activeSessionId.value) {
        failCount += 1
        markScenarioStep(step, 'error', { success: false, error_message: '当前没有 session_id，无法继续执行。' })
        if (scenarioSettings.stopOnFailure) break
        continue
      }
      await handleScenarioStepRun(step)
      const result = scenarioStepResults[step.key]
      if (result?.success === false || result?.status === 'error') {
        failCount += 1
        if (scenarioSettings.stopOnFailure) break
      } else {
        successCount += 1
      }
    }

    const record = {
      id: `${Date.now()}`,
      scenario: activeInterfaceScenario.value.name,
      env: connectionForm.env,
      at: startedAt.toLocaleString(),
      duration: `${Math.max(1, Math.round((Date.now() - startedAt.getTime()) / 1000))}s`,
      success: successCount,
      skipped: skippedCount,
      failed: failCount,
      status: failCount > 0 ? '失败' : '完成',
      context: cloneScenarioPayload(latestScenarioRunContext.value),
      variables: cloneScenarioPayload(scenarioVariables),
      steps: buildScenarioRunStepSnapshots(enabledSteps),
    }
    addScenarioExecutionRecord(record)
    activeScenarioTab.value = 'history'
    pushActivity('scenario', `${record.scenario} 服务端执行${record.status}`, record)
    ElMessage({
      type: failCount > 0 ? 'warning' : 'success',
      message: `${record.scenario} ${record.status}：成功 ${successCount}，跳过 ${skippedCount}，失败 ${failCount}`,
    })
  } finally {
    scenarioExecuting.value = false
  }
}

function syncDowsureFollowupFields(operationKey, data) {
  if (operationKey === 'dowsureCreditResult') {
    if (data.applicationCode) {
      operationForms.dowsureEsignDrawdownResult.application_code = data.applicationCode
      operationForms.dowsureRepaymentResult.application_code = data.applicationCode
    }
    if (Object.prototype.hasOwnProperty.call(data, 'creditContractNo')) {
      operationForms.dowsureEsignDrawdownResult.credit_contract_no = data.creditContractNo
    }
  }

  if (operationKey === 'dowsureEsignDrawdownResult') {
    if (data.applicationCode) {
      operationForms.dowsureRepaymentResult.application_code = data.applicationCode
    }
    if (data.loanCode) {
      operationForms.dowsureRepaymentResult.loan_code = data.loanCode
    }
    if (Object.prototype.hasOwnProperty.call(data, 'loanContractNo')) {
      operationForms.dowsureRepaymentResult.loan_contract_no = data.loanContractNo
    }
  }
}

async function handleAiSend() {
  const text = aiInput.value.trim()
  if (!text || aiSending.value) return
  aiError.value = ''
  aiMessages.value.push({
    id: `${Date.now()}-user`,
    role: 'user',
    content: text,
    at: new Date().toLocaleTimeString(),
  })
  aiInput.value = ''
  aiSending.value = true

  try {
    const history = aiMessages.value
      .filter((item) => ['user', 'assistant', 'tool'].includes(item.role))
      .filter((item) => !item.meta?.error)
      .slice(0, -1)
      .slice(-12)
      .map((item) => ({ role: item.role, content: item.content }))
    const response = await sendAiChat({
      message: text,
      history,
      context: buildAiContext(),
    })

    aiMessages.value.push({
      id: `${Date.now()}-assistant`,
      role: 'assistant',
      content: response.reply || '已完成。',
      at: new Date().toLocaleTimeString(),
      meta: {
        mode: response.mode,
        tool_name: response.tool_name,
        tool_result: response.tool_result,
        missing_fields: response.missing_fields,
      },
    })
  } catch (error) {
    aiError.value = normalizeError(error)
    aiMessages.value.push({
      id: `${Date.now()}-error`,
      role: 'assistant',
      content: `请求失败: ${normalizeError(error)}`,
      at: new Date().toLocaleTimeString(),
      meta: { error: true },
    })
  } finally {
    aiSending.value = false
  }
}

function buildPayload(operation) {
  const payload = { session_id: activeSessionId.value, username: authUser.value?.username }
  if (selectedApplicationUniqueId.value) {
    payload.application_unique_id = selectedApplicationUniqueId.value
  }
  if (['pspStart', 'pspCompleted'].includes(operation.key) && selectedPspMerchantAccountId.value) {
    payload.merchant_account_id = selectedPspMerchantAccountId.value
  }
  const form = operationForms[operation.key] ?? {}
  for (const field of operation.fields) {
    if (field.visible && !field.visible(form)) continue
    const value = form[field.prop]
    if (field.type === 'text') {
      if (value !== undefined && value !== null && String(value).trim() !== '') {
        payload[field.prop] = String(value).trim()
      }
    } else if (value !== undefined && value !== null && value !== '') {
      payload[field.prop] = value
    }
  }
  if (operation.key === 'underwrittenDowsure') {
    payload.merchant_accounts = (form.merchant_accounts ?? [])
      .map((item) => ({
        merchantAccountId: String(item.merchantAccountId ?? '').trim(),
        merchantAccountLimit: item.merchantAccountLimit ?? null,
      }))
      .filter((item) => item.merchantAccountId)
  }
  return payload
}

function pushActivity(kind, title, payload) {
  activityFeed.value.unshift({
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    kind,
    title,
    payload,
    at: new Date().toLocaleString(),
  })
  activityFeed.value = activityFeed.value.slice(0, 30)
}

function clearLogs() {
  eventLogs.value = []
}

function showRegisterToast(type, message) {
  ElMessage({
    type,
    message,
    duration: 2000,
    showClose: true,
  })
}

function showOperationToast(type, title, payload) {
  ElNotification({
    type,
    title,
    message: summarizeOperationResult(payload),
    duration: type === 'success' ? 2600 : 5000,
    showClose: true,
    customClass: type === 'success' ? 'operation-toast-success' : 'operation-toast-error',
  })
}

function buildOperationResult(status, payload, fallbackMessage = '') {
  if (status === 'success') return payload
  if (payload && typeof payload === 'object') {
    return {
      success: false,
      ...payload,
      error_message: payload.error_message || payload.message || payload.detail || fallbackMessage || null,
    }
  }
  return {
    success: false,
    error_message: fallbackMessage || String(payload || '未知错误'),
  }
}

function getErrorPayload(error) {
  return error?.payload || error?.response?.data || null
}

function summarizeOperationResult(payload) {
  if (payload && typeof payload === 'object') {
    return payload.error_message || payload.message || payload.detail || JSON.stringify(payload).slice(0, 180)
  }
  return String(payload || '')
}

function openLogSystem() {
  if (!requireAdminView('logs')) return
  closeToolRail()
  currentView.value = 'logs'
  runLogSearch()
}

function openInterfaceTestView() {
  closeToolRail()
  currentView.value = 'interfaceTest'
  if (!activeOperationKey.value && activeInterfaceScenario.value.steps.length > 0) {
    activeOperationKey.value = activeInterfaceScenario.value.steps[0].key
  }
}

function backToConsole() {
  currentView.value = 'console'
}

function openAboutView() {
  closeToolRail()
  currentView.value = 'about'
}

function openContactView() {
  closeToolRail()
  currentView.value = 'contact'
}

function openContactAdminView() {
  if (!requireAdminView('contactAdmin')) return
  closeToolRail()
  currentView.value = 'contactAdmin'
}

function toggleToolRail() {
  toolRailOpen.value = !toolRailOpen.value
}

function closeToolRail() {
  toolRailOpen.value = false
}

function resetLogSearch() {
  logSearchForm.keyword = ''
  logSearchForm.timeRange = []
  logSearchForm.limit = 500
  runLogSearch()
}

async function runLogSearch() {
  logSearchLoading.value = true
  try {
    const [startTime, endTime] = logSearchForm.timeRange || []
    logSearchResults.value = await fetchLogs({
      keyword: logSearchForm.keyword || undefined,
      start_time: startTime || undefined,
      end_time: endTime || undefined,
      session_id: activeSessionId.value || undefined,
      limit: logSearchForm.limit,
    })
  } catch (error) {
    pushActivity('error', '日志查询失败', normalizeError(error))
  } finally {
    logSearchLoading.value = false
  }
}

function clearAiChat() {
  aiMessages.value = []
  aiError.value = ''
}

function openAiPage() {
  closeToolRail()
  aiExecutionEnv.value = sessionSummary.value?.env || connectionForm.env || registerForm.env || 'reg'
  currentView.value = 'ai'
}

async function handleLogin() {
  const username = loginForm.username.trim()
  const password = loginForm.password.trim()
  if (!username || !password) {
    loginError.value = '请输入账号和密码'
    return
  }

  let user
  try {
    user = await loginUser({ username, password })
  } catch (error) {
    loginError.value = normalizeError(error)
    return
  }

  authUser.value = {
    username: user.username,
    role: user.role,
    login_at: new Date().toLocaleString(),
  }
  window.localStorage.setItem(authStorageKey, JSON.stringify(authUser.value))
  loginError.value = ''
  loginForm.password = ''
  currentView.value = 'console'
  closeToolRail()
  pushActivity('auth', user.role === 'admin' ? '管理员已登录' : '用户已登录', {
    username: user.username,
    role: user.role,
  })
}

function openRegisterPage() {
  authMode.value = 'register'
  loginError.value = ''
  registerError.value = ''
  userRegisterForm.username = loginForm.username.trim()
  userRegisterForm.password = ''
  userRegisterForm.answer = ''
  refreshCaptchaChallenge()
}

function openLoginPage() {
  authMode.value = 'login'
  loginError.value = ''
  registerError.value = ''
  userRegisterForm.password = ''
  userRegisterForm.answer = ''
}

function refreshCaptchaChallenge() {
  captchaChallenge.left = Math.floor(Math.random() * 8) + 2
  captchaChallenge.right = Math.floor(Math.random() * 8) + 2
  userRegisterForm.answer = ''
}

async function handleUserRegister() {
  const username = userRegisterForm.username.trim()
  const password = userRegisterForm.password.trim()
  const answer = Number(userRegisterForm.answer)
  const expected = captchaChallenge.left + captchaChallenge.right

  if (!username || !password) {
    registerError.value = '请输入账号和密码'
    return
  }
  if (username === 'admin') {
    registerError.value = 'admin 为管理员账号，不能注册'
    return
  }
  if (!Number.isFinite(answer) || answer !== expected) {
    registerError.value = '验证答案不正确'
    refreshCaptchaChallenge()
    return
  }

  try {
    await registerUser({ username, password })
  } catch (error) {
    registerError.value = normalizeError(error)
    return
  }

  registerError.value = ''
  ElMessageBox.alert('注册成功，请使用新账号登录。', '注册成功', {
    confirmButtonText: '返回登录',
    type: 'success',
    callback: () => {
      loginForm.username = username
      loginForm.password = ''
      openLoginPage()
    },
  })
}

function handleLogout() {
  const username = authUser.value?.username
  authUser.value = null
  window.localStorage.removeItem(authStorageKey)
  currentView.value = 'console'
  closeToolRail()
  closeSocket()
  stopSessionPolling()
  pushActivity('auth', '用户已退出', { username })
}

function restoreAuthUser() {
  const raw = window.localStorage.getItem(authStorageKey)
  if (!raw) return
  try {
    const saved = JSON.parse(raw)
    if (!saved?.username || !['admin', 'user'].includes(saved.role)) return
    authUser.value = saved
    currentView.value = 'console'
  } catch (error) {
    window.localStorage.removeItem(authStorageKey)
    console.warn('Failed to restore auth user', error)
  }
}

function requireAdminView(fallbackView = 'ai') {
  if (isAdmin.value) return true
  currentView.value = fallbackView === 'logs' || fallbackView === 'contactAdmin' ? 'ai' : fallbackView
  ElMessage({
    type: 'warning',
    message: '当前账号无管理员权限',
    duration: 2200,
    showClose: true,
  })
  return false
}

function isPspRowSelectable(row) {
  return String(row?.psp_status || '').toUpperCase() !== 'SUCCESS'
}

function selectPspAuthorizationRow(row) {
  if (!isPspRowSelectable(row)) return
  selectedPspMerchantAccountId.value = row.merchant_account_id
  pspSelectionTouched.value = true
}

function useAiPrompt(prompt) {
  aiInput.value = prompt
}

async function submitContactIssue() {
  const issue = contactForm.issue.trim()
  if (!issue) {
    pushActivity('contact', '问题内容为空', '请先输入需要反馈的问题。')
    return
  }
  try {
    const contactIssue = await createContactIssue({
      created_by: authUser.value?.username,
      issue,
      env: sessionSummary.value?.env || connectionForm.env,
      phone_number: sessionSummary.value?.phone_number || connectionForm.phone_number || null,
      session_id: activeSessionId.value || null,
      merchant_id: sessionSummary.value?.merchant_id || null,
    })
    contactIssues.value.unshift(contactIssue)
    pushActivity('contact', '已留下问题', contactIssue)
    contactForm.issue = ''
  } catch (error) {
    pushActivity('error', '提交问题失败', normalizeError(error))
  }
}

function handleContactAdminLogin() {
  const username = contactAdminForm.username.trim()
  const password = contactAdminForm.password.trim()
  if (username === 'admin' && password === 'admin') {
    contactAdminLoggedIn.value = true
    contactAdminError.value = ''
    contactAdminForm.password = ''
    pushActivity('contact', '联系我们管理员已登录', { username })
    return
  }
  contactAdminError.value = '账号或密码不正确'
}

function handleContactAdminLogout() {
  contactAdminLoggedIn.value = false
  contactAdminForm.username = ''
  contactAdminForm.password = ''
  contactAdminForm.reply = ''
  contactAdminError.value = ''
}

async function replyContactIssue(issue) {
  const reply = contactAdminForm.reply.trim()
  if (!reply) {
    contactAdminError.value = '请先填写回复内容'
    return
  }
  try {
    const updated = await replyContactIssueApi(issue.id, {
      reply,
      replied_by: authUser.value?.username,
    })
    const index = contactIssues.value.findIndex((item) => item.id === issue.id)
    if (index >= 0) contactIssues.value[index] = updated
    contactAdminForm.reply = ''
    contactAdminError.value = ''
    pushActivity('contact', '已回复联系我们问题', {
      issue_id: issue.id,
      reply,
    })
  } catch (error) {
    contactAdminError.value = normalizeError(error)
  }
}

async function deleteContactIssue(issueId) {
  const target = contactIssues.value.find((item) => item.id === issueId)
  if (!target) return
  const confirmed = window.confirm('确认删除这个问题吗？删除后不会再展示在问题记录里。')
  if (!confirmed) return
  try {
    await deleteContactIssueApi(issueId)
    contactIssues.value = contactIssues.value.filter((item) => item.id !== issueId)
    contactAdminError.value = ''
    pushActivity('contact', '已删除联系我们问题', {
      issue_id: issueId,
      status: target.status,
    })
  } catch (error) {
    contactAdminError.value = normalizeError(error)
  }
}

async function loadContactIssues() {
  try {
    contactIssues.value = await fetchContactIssues()
  } catch (error) {
    console.warn('Failed to load contact issues', error)
  }
}

function connectLogs(sessionId) {
  closeSocket()
  wsError.value = ''
  wsConnected.value = false
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const socketUrl = `${protocol}//${window.location.host}/ws/logs/${sessionId}`
  logSocket = new WebSocket(socketUrl)

  logSocket.onopen = () => {
    wsConnected.value = true
  }
  logSocket.onmessage = (event) => {
    try {
      eventLogs.value.unshift(JSON.parse(event.data))
      eventLogs.value = eventLogs.value.slice(0, 300)
    } catch {
      eventLogs.value.unshift({
        timestamp: new Date().toLocaleString(),
        level: 'INFO',
        formatted: event.data,
      })
    }
  }
  logSocket.onerror = () => {
    wsError.value = 'WebSocket 连接失败'
    wsConnected.value = false
  }
  logSocket.onclose = () => {
    wsConnected.value = false
  }
}

function closeSocket() {
  if (logSocket) {
    logSocket.close()
    logSocket = null
  }
}

function normalizeError(error) {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  return error?.message || '未知错误'
}

function toggleOperationPanel(key) {
  activeOperationKey.value = activeOperationKey.value === key ? '' : key
}

function levelTagType(level) {
  if (level === 'ERROR') return 'danger'
  if (level === 'WARNING') return 'warning'
  if (level === 'INFO') return 'success'
  return 'info'
}

function fieldOptions(field) {
  return (field.options ?? []).map((option) => (
    typeof option === 'object' ? option : { label: option, value: option }
  ))
}

function journeyLabel(journey) {
  return journeyLabels[journey] ?? journey
}

async function establishSession(payload, title = '会话连接成功') {
  const data = await connectSession({
    ...payload,
    username: authUser.value?.username,
  })
  activeSessionId.value = data.session_id
  selectedApplicationUniqueId.value = data.selected_application_unique_id || data.application_unique_id || data.applications?.[0]?.application_unique_id || ''
  pushActivity('connect', title, data)
  await loadSessions()
  connectLogs(data.session_id)
  startSessionPolling()
  return data
}

async function connectAfterRegister(phoneNumber, env) {
  const attempts = 4
  let lastError = null

  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      return await establishSession(
        { env, phone_number: phoneNumber },
        attempt === 1 ? '注册后已自动连接会话' : `注册后自动连接成功，第 ${attempt} 次重试成功`,
      )
    } catch (error) {
      lastError = error
      if (attempt < attempts) {
        await new Promise((resolve) => window.setTimeout(resolve, 1200))
      }
    }
  }

  throw lastError
}

function buildAiContext() {
  return {
    active_session_id: activeSessionId.value,
    session: sessionSummary.value,
    selected_application_unique_id: selectedApplicationUniqueId.value,
    selected_application: selectedApplication.value,
    selected_env: aiExecutionEnv.value,
    selected_register_env: registerForm.env,
    selected_currency: registerForm.currency,
    selected_funder_resource: registerForm.funder_resource,
    preferred_currency: sessionSummary.value?.preferred_currency,
    selected_journey: registerForm.journey,
    recent_logs: eventLogs.value.slice(0, 20),
    recent_activities: activityFeed.value.slice(0, 12),
  }
}
</script>

<template>
  <div class="app-shell" :class="{ 'theme-dark': darkMode }">
    <section v-if="!isAuthenticated" class="login-view">
      <el-card shadow="never" class="login-panel">
        <template #header>
          <div class="login-head">
            <div>
              <p class="eyebrow">DPU Mock Console</p>
              <h1>登录 Mock API 操作台</h1>
            </div>
            <div class="login-theme-toggle" title="切换深色/浅色模式">
              <el-icon><Moon v-if="darkMode" /><Sunny v-else /></el-icon>
              <el-switch v-model="darkMode" size="small" />
            </div>
          </div>
        </template>

        <div class="login-grid login-grid-single">
          <el-form v-if="authMode === 'login'" label-position="top" class="tight-form login-form" @submit.prevent="handleLogin">
            <el-form-item label="账号">
              <el-input v-model.trim="loginForm.username" :prefix-icon="User" autocomplete="username" />
            </el-form-item>
            <el-form-item label="密码">
              <el-input
                v-model="loginForm.password"
                type="password"
                show-password
                autocomplete="current-password"
                @keydown.enter.prevent="handleLogin"
              />
            </el-form-item>
            <p v-if="loginError" class="login-error">{{ loginError }}</p>
            <el-button type="primary" :icon="Connection" native-type="submit">登录</el-button>
          </el-form>

          <el-form v-else label-position="top" class="tight-form login-form register-form" @submit.prevent="handleUserRegister">
            <el-form-item label="账号">
              <el-input v-model.trim="userRegisterForm.username" :prefix-icon="User" autocomplete="username" />
            </el-form-item>
            <el-form-item label="密码">
              <el-input
                v-model="userRegisterForm.password"
                type="password"
                show-password
                autocomplete="new-password"
                @keydown.enter.prevent="handleUserRegister"
              />
            </el-form-item>
            <el-form-item :label="`验证题：${captchaChallenge.left} + ${captchaChallenge.right} = ?`">
              <div class="captcha-row">
                <el-input
                  v-model.trim="userRegisterForm.answer"
                  inputmode="numeric"
                  @keydown.enter.prevent="handleUserRegister"
                />
                <el-button plain @click="refreshCaptchaChallenge">换一题</el-button>
              </div>
            </el-form-item>
            <p v-if="registerError" class="login-error">{{ registerError }}</p>
            <el-button type="primary" :icon="User" native-type="submit">注册</el-button>
          </el-form>
        </div>
        <div class="login-footer-action">
          <button v-if="authMode === 'login'" type="button" @click="openRegisterPage">注册账号</button>
          <button v-else type="button" @click="openLoginPage">返回登录</button>
        </div>
      </el-card>
    </section>

    <template v-else>
    <button
      class="tool-edge-toggle"
      :class="{ active: toolRailOpen }"
      type="button"
      :title="toolRailOpen ? '收起工具入口' : '展开工具入口'"
      :aria-label="toolRailOpen ? '收起工具入口' : '展开工具入口'"
      @click="toggleToolRail"
    >
      <el-icon><Fold v-if="toolRailOpen" /><Expand v-else /></el-icon>
      <span>{{ toolRailOpen ? '收起工具' : '展开工具' }}</span>
    </button>
    <div v-if="toolRailOpen" class="tool-rail-scrim" @click="closeToolRail"></div>
    <aside class="tool-side-rail" :class="{ open: toolRailOpen }" aria-label="工具入口">
      <div class="tool-side-rail-head">
        <span>工具入口</span>
        <button type="button" aria-label="收起工具入口" @click="closeToolRail">
          <el-icon><Fold /></el-icon>
        </button>
      </div>
      <div class="side-user-card" title="当前登录账号">
        <span class="side-user-avatar">
          <el-icon><User /></el-icon>
        </span>
        <span class="side-user-meta">
          <strong>{{ authDisplayName }}</strong>
          <small>{{ authRoleLabel }}</small>
        </span>
      </div>
      <button class="side-tool-action tone-console" :class="{ active: currentView === 'console' }" type="button" @click="backToConsole">
        <el-icon><Monitor /></el-icon>
        <span>Mock 控制台</span>
      </button>
      <button class="side-tool-action tone-api" :class="{ active: activeToolModule === 'interfaceTest' }" type="button" @click="openInterfaceTestView">
        <el-icon><Tickets /></el-icon>
        <span>接口测试</span>
      </button>
      <button v-if="isAdmin" class="side-tool-action tone-logs" :class="{ active: activeToolModule === 'logs' }" type="button" @click="openLogSystem">
        <el-icon><Search /></el-icon>
        <span>日志系统</span>
      </button>
      <button class="side-tool-action tone-ai" :class="{ active: activeToolModule === 'ai' }" type="button" @click="openAiPage">
        <el-icon><ChatLineRound /></el-icon>
        <span>AI 助手</span>
      </button>
      <button class="side-tool-action tone-about" :class="{ active: activeToolModule === 'about' }" type="button" @click="openAboutView">
        <el-icon><Document /></el-icon>
        <span>关于我们</span>
      </button>
      <button class="side-tool-action tone-contact" :class="{ active: activeToolModule === 'contact' }" type="button" @click="openContactView">
        <el-icon><Position /></el-icon>
        <span>联系我们</span>
      </button>
      <button v-if="isAdmin" class="side-tool-action tone-reply" :class="{ active: activeToolModule === 'contactAdmin' }" type="button" @click="openContactAdminView">
        <el-icon><Connection /></el-icon>
        <span>回复问题</span>
      </button>
      <button class="side-tool-action logout-action" type="button" @click="handleLogout">
        <el-icon><SwitchButton /></el-icon>
        <span>退出登录</span>
      </button>
    </aside>
    <section class="hero-panel">
      <button
        class="hero-tool-toggle"
        :class="{ active: activeToolModule }"
        type="button"
        :title="toolRailCollapsed ? '展开工具入口' : '收起工具入口'"
        :aria-label="toolRailCollapsed ? '展开工具入口' : '收起工具入口'"
        @click="toggleToolRail"
      >
        <el-icon><Expand v-if="toolRailCollapsed" /><Fold v-else /></el-icon>
        <span>{{ toolRailCollapsed ? '展开工具' : '收起工具' }}</span>
      </button>
      <div>
        <p class="eyebrow">DPU Mock Console</p>
        <h1>DPU Mock API 操作台</h1>
        <p class="hero-copy">
          连接账号、触发 workflow webhook、查看实时日志；所有操作都绑定当前环境和 session。
        </p>
        <div class="hero-status-grid" aria-label="console status">
          <div
            v-for="card in consoleStatusCards"
            :key="card.label"
            class="status-card"
            :class="`tone-${card.tone}`"
          >
            <span>{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
            <code>{{ card.detail }}</code>
          </div>
        </div>
      </div>
      <div class="hero-action-stack">
        <div class="hero-action hero-theme-toggle" title="切换深色/浅色模式">
          <el-icon><Moon v-if="darkMode" /><Sunny v-else /></el-icon>
          <span>{{ darkMode ? '深色模式' : '浅色模式' }}</span>
          <el-switch v-model="darkMode" size="small" />
        </div>
        <div class="hero-action hero-user-chip" title="当前登录账号">
          <el-icon><User /></el-icon>
          <span>{{ authDisplayName }}</span>
          <el-tag size="small" :type="isAdmin ? 'success' : 'info'" effect="plain">{{ isAdmin ? '管理员' : '用户' }}</el-tag>
        </div>
        <button
          class="hero-action tool-toggle-action"
          :class="{ active: activeToolModule }"
          type="button"
          :title="toolRailCollapsed ? '展开工具入口' : '收起工具入口'"
          :aria-label="toolRailCollapsed ? '展开工具入口' : '收起工具入口'"
          @click="toggleToolRail"
        >
          <el-icon><Expand v-if="toolRailCollapsed" /><Fold v-else /></el-icon>
          <span>{{ toolRailCollapsed ? '展开工具' : '收起工具' }}</span>
        </button>
        <template v-if="!toolRailCollapsed">
          <div class="hero-action hero-theme-toggle" title="切换深色/浅色模式">
            <el-icon><Moon v-if="darkMode" /><Sunny v-else /></el-icon>
            <span>{{ darkMode ? '深色模式' : '浅色模式' }}</span>
            <el-switch v-model="darkMode" size="small" />
          </div>
          <button class="hero-action" :class="{ active: currentView === 'console' }" type="button" @click="backToConsole">
            <el-icon><Monitor /></el-icon>
            <span>Mock 控制台</span>
          </button>
          <button class="hero-action" :class="{ active: activeToolModule === 'interfaceTest' }" type="button" @click="openInterfaceTestView">
            <el-icon><Tickets /></el-icon>
            <span>接口测试</span>
          </button>
          <button v-if="isAdmin" class="hero-action" :class="{ active: activeToolModule === 'logs' }" type="button" @click="openLogSystem">
            <el-icon><Search /></el-icon>
            <span>日志系统</span>
          </button>
          <button class="hero-action" :class="{ active: activeToolModule === 'ai' }" type="button" @click="openAiPage">
            <el-icon><ChatLineRound /></el-icon>
            <span>AI 助手</span>
          </button>
          <button class="hero-action" :class="{ active: activeToolModule === 'about' }" type="button" @click="openAboutView">
            <el-icon><Document /></el-icon>
            <span>关于我们</span>
          </button>
          <button class="hero-action" :class="{ active: activeToolModule === 'contact' }" type="button" @click="openContactView">
            <el-icon><Position /></el-icon>
            <span>联系我们</span>
          </button>
          <button v-if="isAdmin" class="hero-action" :class="{ active: activeToolModule === 'contactAdmin' }" type="button" @click="openContactAdminView">
            <el-icon><Connection /></el-icon>
            <span>回复问题</span>
          </button>
          <button class="hero-action" type="button" @click="handleLogout">
            <el-icon><SwitchButton /></el-icon>
            <span>退出</span>
          </button>
        </template>
      </div>
    </section>


    <section v-if="currentView === 'interfaceTest'" class="interface-test-view">
      <div class="log-system-head interface-test-head">
        <div>
          <p class="eyebrow">Interface Test</p>
          <h2>接口测试</h2>
          <p>按 workflow 顺序列出所有 mock 接口，选择接口后可查看请求参数、预览 payload 并直接发起调用。</p>
        </div>
        <div class="interface-test-actions">
          <el-tag :type="activeSessionId ? 'success' : 'warning'" effect="plain">{{ activeSessionId ? 'Session 已连接' : '未连接 Session' }}</el-tag>
          <el-button plain :icon="Refresh" @click="backToConsole">返回控制台</el-button>
        </div>
      </div>

      <div v-if="false" class="interface-session-strip">
        <section class="interface-session-card">
          <div class="interface-session-head">
            <div>
              <h3>会话连接</h3>
              <p>自动化执行会自行注册并建立 session，也可以手动绑定已有手机号。</p>
            </div>
            <el-tag :type="activeSessionId ? 'success' : 'warning'" effect="plain">{{ activeSessionId ? '已连接' : '未连接' }}</el-tag>
          </div>
          <div class="interface-session-form">
            <el-select v-model="connectionForm.env" aria-label="连接环境">
              <el-option
                v-for="env in enumOptions?.environments ?? defaultEnvironments"
                :key="`api-connect-${env}`"
                :label="env"
                :value="env"
              />
            </el-select>
            <el-input v-model.trim="connectionForm.phone_number" placeholder="8位或11位数字" />
            <el-button type="primary" :icon="Connection" :loading="connecting" @click="handleConnect">连接 session</el-button>
          </div>
        </section>

        <section class="interface-session-card">
          <div class="interface-session-head">
            <div>
              <h3>新账号注册</h3>
              <p>注册完成后会自动尝试连接，可直接继续接口测试。</p>
            </div>
            <el-switch v-model="registerForm.offline" active-text="线下模式" inactive-text="线上模式" />
          </div>
          <div class="interface-register-form">
            <el-select v-model="registerForm.env" aria-label="注册环境">
              <el-option
                v-for="env in enumOptions?.environments ?? defaultEnvironments"
                :key="`api-reg-${env}`"
                :label="env"
                :value="env"
              />
            </el-select>
            <el-select v-if="!registerForm.offline" v-model="registerForm.journey" aria-label="Journey">
              <el-option
                v-for="journey in enumOptions?.journeys ?? defaultJourneys"
                :key="`api-journey-${journey}`"
                :label="journeyLabel(journey)"
                :value="journey"
              />
            </el-select>
            <el-select v-model="registerForm.currency" aria-label="币种">
              <el-option
                v-for="currency in enumOptions?.currencies ?? defaultCurrencies"
                :key="`api-currency-${currency}`"
                :label="currency"
                :value="currency"
              />
            </el-select>
            <el-select v-model="registerForm.funder_resource" aria-label="资方代码">
              <el-option
                v-for="resource in enumOptions?.funder_resources ?? defaultFunderResources"
                :key="`api-funder-${resource}`"
                :label="resource"
                :value="resource"
              />
            </el-select>
            <el-button type="success" :icon="Promotion" :loading="registering" @click="handleRegister">执行注册</el-button>
            <el-button type="warning" plain :icon="Link" :loading="registeringAndBinding" @click="handleRegisterAndRunMultiShop">注册并完成绑店</el-button>
          </div>
        </section>
      </div>

      <div class="interface-automation-shell">
        <aside class="scenario-library" aria-label="场景集合">
          <div class="scenario-actions">
            <el-button type="primary" @click="handleScenarioCreate">新建场景</el-button>
            <el-button plain @click="handleScenarioImport">导入场景</el-button>
          </div>
          <el-input placeholder="请输入模块名称进行搜索" />
          <div class="scenario-tree">
            <div class="scenario-tree-head">
              <strong>全部场景 ({{ interfaceScenarios.length }})</strong>
              <el-tag size="small" effect="plain">DPU产品流程</el-tag>
            </div>
            <button
              v-for="scenario in interfaceScenarios"
              :key="scenario.key"
              class="scenario-node"
              :class="{ active: activeInterfaceScenarioKey === scenario.key }"
              type="button"
              @click="activeInterfaceScenarioKey = scenario.key"
            >
              <span>{{ scenario.name }}</span>
              <small>{{ scenario.steps.length }} 步骤</small>
            </button>
          </div>
        </aside>

        <main class="scenario-workbench">
          <div class="scenario-toolbar">
            <div class="scenario-title-block">
              <div class="scenario-status-line">
                <strong>{{ activeInterfaceScenario.name }}</strong>
              </div>
              <p>{{ activeInterfaceScenario.description }} · {{ enabledInterfaceStepCount }} / {{ interfaceAutomationSteps.length }} 个步骤启用</p>
            </div>
            <div class="scenario-run-actions">
              <el-select v-model="connectionForm.env" class="scenario-env-select" aria-label="执行环境">
                <el-option
                  v-for="env in enumOptions?.environments ?? defaultEnvironments"
                  :key="`scenario-env-${env}`"
                  :label="env"
                  :value="env"
                />
              </el-select>
              <el-button type="primary" :icon="Promotion" :loading="scenarioExecuting" @click="handleScenarioServerExecute">服务端执行</el-button>
              <el-button type="primary" plain @click="handleScenarioSave">保存</el-button>
            </div>
          </div>

          <section v-if="latestScenarioRunContext" class="scenario-panel scenario-run-context">
            <div><span>执行环境</span><strong>{{ latestScenarioRunContext.env || '-' }}</strong></div>
            <div><span>手机号</span><strong>{{ latestScenarioRunContext.phone_number || '-' }}</strong></div>
            <div><span>Merchant ID</span><strong>{{ latestScenarioRunContext.merchant_id || '-' }}</strong></div>
            <div><span>Application Unique ID</span><strong>{{ latestScenarioRunContext.application_unique_id || '-' }}</strong></div>
          </section>

          <div class="scenario-tabs">
            <button
              v-for="tab in scenarioTabs"
              :key="tab.key"
              type="button"
              :class="{ active: activeScenarioTab === tab.key }"
              @click="activeScenarioTab = tab.key"
            >{{ tab.label }}</button>
          </div>

          <section v-if="activeScenarioTab === 'base'" class="scenario-panel scenario-base-panel">
            <div><span>场景名称</span><strong>{{ activeInterfaceScenario.name }}</strong></div>
            <div><span>场景编号</span><strong>{{ activeInterfaceScenario.code }}</strong></div>
            <div><span>优先级</span><strong>{{ activeInterfaceScenario.priority }}</strong></div>
            <div><span>执行环境</span><strong>{{ connectionForm.env }}</strong></div>
            <div><span>保存状态</span><strong>{{ scenarioSaveState }}</strong></div>
            <div><span>步骤启用</span><strong>{{ enabledInterfaceStepCount }} / {{ interfaceAutomationSteps.length }}</strong></div>
          </section>

          <section v-else-if="activeScenarioTab === 'params'" class="scenario-panel">
            <div class="scenario-panel-head">
              <strong>场景变量</strong>
              <span>变量会在执行时注入到请求体和脚本上下文。</span>
            </div>
            <div class="scenario-variable-table">
              <div><span>Key</span><span>Value</span><span>Scope</span></div>
              <div v-for="(value, key) in scenarioVariables" :key="key">
                <strong>{{ key }}</strong>
                <el-input v-model="scenarioVariables[key]" />
                <span>Scenario</span>
              </div>
            </div>
          </section>

          <section v-else-if="activeScenarioTab === 'hooks'" class="scenario-panel scenario-hooks-panel">
            <div>
              <strong>前置操作</strong>
              <p>初始化 env、session、手机号、merchant 变量；校验当前用户登录状态。</p>
            </div>
            <div>
              <strong>后置操作</strong>
              <p>写入执行历史、刷新会话摘要、保留最近响应和错误信息。</p>
            </div>
          </section>

          <section v-else-if="activeScenarioTab === 'assertions'" class="scenario-panel">
            <div class="scenario-panel-head">
              <strong>统一断言</strong>
              <span>执行结果需要同时满足 HTTP、业务成功和 trace 信息。</span>
            </div>
            <div class="scenario-assertion-list">
              <label v-for="assertion in scenarioAssertions" :key="assertion.target">
                <el-checkbox v-model="assertion.enabled" />
                <strong>{{ assertion.target }}</strong>
                <span>{{ assertion.rule }}</span>
              </label>
            </div>
          </section>

          <section v-else-if="activeScenarioTab === 'history'" class="scenario-panel">
            <div class="scenario-panel-head">
              <strong>执行历史</strong>
              <span>本机持续保留服务端执行记录。</span>
            </div>
            <div v-if="scenarioExecutionHistory.length === 0" class="scenario-empty">暂无执行历史。</div>
            <div v-for="item in scenarioExecutionHistory" :key="item.id" class="scenario-history-row">
              <el-tag :type="item.status === '完成' ? 'success' : item.status === '未执行' ? 'warning' : 'danger'" effect="plain">{{ item.status }}</el-tag>
              <strong>{{ item.scenario }}</strong>
              <span>{{ item.env }}</span>
              <span>{{ item.at }}</span>
              <span>成功 {{ item.success }} / 跳过 {{ item.skipped }} / 失败 {{ item.failed }}</span>
              <code>{{ item.duration }}</code>
              <el-button size="small" plain @click="openScenarioHistoryDetail(item)">详情</el-button>
            </div>
          </section>

          <section v-else-if="activeScenarioTab === 'settings'" class="scenario-panel scenario-settings-panel">
            <label><span>失败后停止</span><el-switch v-model="scenarioSettings.stopOnFailure" /></label>
            <label><span>保存响应详情</span><el-switch v-model="scenarioSettings.saveResponse" /></label>
            <label><span>执行前校验 session</span><el-switch v-model="scenarioSettings.validateSession" /></label>
            <label><span>默认超时</span><el-input v-model="scenarioSettings.timeout" /></label>
          </section>

          <template v-else>
          <div class="scenario-step-summary">
            <el-checkbox />
            <span>共 {{ interfaceAutomationSteps.length }} 个步骤</span>
            <el-button size="small" text :icon="Refresh" @click="loadSessions">刷新</el-button>
          </div>

          <section class="scenario-step-list">
            <article
              v-for="step in interfaceAutomationSteps"
              :key="`scenario-step-${step.key}`"
              class="scenario-step-row"
              :class="{ active: selectedInterfaceStep?.key === step.key, disabled: !step.enabled }"
            >
              <div class="scenario-step-main" @click="toggleScenarioStep(step)">
                <el-checkbox />
                <span class="step-index">{{ step.order }}</span>
                <el-switch v-model="interfaceStepEnabled[step.key]" />
                <button class="step-run-button" type="button" :disabled="(step.type === 'api' && !activeSessionId) || runningOperationKey === step.operation?.key" @click.stop="handleScenarioStepRun(step)">
                  <el-icon><Promotion /></el-icon>
                </button>
                <span class="step-state" :class="scenarioStepResults[step.key]?.status || 'idle'"></span>
                <el-tag class="step-kind-tag" size="small" effect="plain" :type="step.type === 'script' ? 'success' : 'primary'">{{ step.kind }}</el-tag>
                <span class="step-method" :class="{ script: step.type === 'script' }">{{ step.method || 'SCRIPT' }}</span>
                <strong class="step-title" :title="step.title">{{ step.title }}</strong>
                <code class="step-endpoint" :title="step.endpoint">{{ step.endpoint }}</code>
                <span class="step-result-tag" :class="scenarioStepResults[step.key]?.status || 'idle'">
                  {{
                    scenarioStepResults[step.key]?.status === 'success'
                      ? '成功'
                      : scenarioStepResults[step.key]?.status === 'error'
                        ? '失败'
                        : '未执行'
                  }}
                </span>
                <button class="step-expand-button" type="button" @click.stop="toggleScenarioStep(step)">
                  <el-icon><ArrowDown v-if="expandedScenarioSteps[step.key]" /><ArrowRight v-else /></el-icon>
                  <span>{{ expandedScenarioSteps[step.key] ? '收起' : '展开' }}</span>
                </button>
              </div>

              <div v-if="hasScenarioStepDetail(step)" v-show="expandedScenarioSteps[step.key]" class="scenario-step-detail">
                <div class="request-tab-row" aria-label="步骤配置">
                  <button
                    type="button"
                    :class="{ active: getScenarioStepDetailTab(step) === 'params' }"
                    @click="setScenarioStepDetailTab(step, 'params')"
                  >Params</button>
                  <button
                    type="button"
                    :class="{ active: getScenarioStepDetailTab(step) === 'body' }"
                    @click="setScenarioStepDetailTab(step, 'body')"
                  >Body</button>
                  <button
                    type="button"
                    :class="{ active: getScenarioStepDetailTab(step) === 'response' }"
                    @click="setScenarioStepDetailTab(step, 'response')"
                  >Response</button>
                </div>
                <div v-if="getScenarioStepDetailTab(step) === 'params'" class="scenario-step-description">
                  <div class="scenario-description-head">
                    <div>
                      <strong>{{ getScenarioStepDescription(step).title }}</strong>
                      <p>{{ getScenarioStepDescription(step).description }}</p>
                    </div>
                    <el-tag size="small" effect="plain">{{ getScenarioStepDescription(step).kind }}</el-tag>
                  </div>
                  <div class="scenario-description-grid">
                    <div>
                      <span>Method</span>
                      <code>{{ getScenarioStepDescription(step).method }}</code>
                    </div>
                    <div>
                      <span>Endpoint</span>
                      <code>{{ getScenarioStepDescription(step).endpoint }}</code>
                    </div>
                    <div>
                      <span>Fields</span>
                      <strong>{{ getScenarioStepDescription(step).fieldCount }} 个参数</strong>
                    </div>
                  </div>
                  <div v-if="getScenarioStepDescription(step).fields.length" class="scenario-field-summary">
                    <div
                      v-for="field in getScenarioStepDescription(step).fields"
                      :key="`scenario-field-summary-${step.key}-${field.prop}`"
                    >
                      <strong>{{ field.label }}</strong>
                      <code>{{ field.prop }}</code>
                      <span>{{ field.type }}</span>
                    </div>
                  </div>
                </div>
                <div v-else-if="getScenarioStepDetailTab(step) === 'body'" class="response-block">
                  <div class="response-block-head">
                    <strong>Request Body</strong>
                    <el-tag size="small" effect="plain">JSON</el-tag>
                  </div>
                  <pre>{{ JSON.stringify(getScenarioStepRequestBody(step), null, 2) }}</pre>
                </div>
                <div v-else class="response-block">
                  <div class="response-block-head">
                    <strong>Response</strong>
                    <el-tag
                      size="small"
                      :type="getScenarioResponseState(step).type"
                      effect="plain"
                    >{{ getScenarioResponseState(step).label }}</el-tag>
                  </div>
                  <pre v-if="getScenarioStepResponse(step)">{{ JSON.stringify(getScenarioStepResponse(step), null, 2) }}</pre>
                  <div v-else class="response-empty">执行该步骤后在这里查看最新响应。</div>
                </div>
              </div>
            </article>
            <button class="scenario-add-step" type="button" @click="handleScenarioAddStep">+ 添加步骤</button>
          </section>
          </template>
        </main>
      </div>
    </section>

    <section v-else-if="currentView === 'logs'" class="log-system-view">
      <div class="log-system-head">
        <div>
          <p class="eyebrow">Log System</p>
          <h2>日志系统</h2>
          <p>按时间和关键字检索 mock 控台调用日志，包括请求方式、URL、请求体、响应体和异常信息。</p>
        </div>
        <el-button plain :icon="Refresh" @click="backToConsole">返回控制台</el-button>
      </div>

      <div class="log-search-bar">
        <el-input
          v-model.trim="logSearchForm.keyword"
          clearable
          placeholder="模糊搜索：URL / 请求体 / 响应体 / 手机号 / merchant / error"
          @keyup.enter="runLogSearch"
        />
        <el-date-picker
          v-model="logSearchForm.timeRange"
          type="datetimerange"
          range-separator="至"
          start-placeholder="开始时间"
          end-placeholder="结束时间"
          value-format="YYYY-MM-DD HH:mm:ss"
        />
        <el-input-number v-model="logSearchForm.limit" :min="50" :max="2000" :step="50" controls-position="right" />
        <el-button type="primary" :loading="logSearchLoading" @click="runLogSearch">查询</el-button>
        <el-button plain @click="resetLogSearch">重置</el-button>
      </div>

      <div class="log-results">
        <div class="log-results-meta">
          <strong>{{ logSearchResults.length }}</strong>
          <span>条匹配日志</span>
          <el-tag :type="wsConnected ? 'success' : 'warning'">{{ logStatusText }}</el-tag>
        </div>
        <div v-if="logSearchResults.length === 0" class="log-empty">暂无匹配日志，执行一次 mock 操作后再搜索。</div>
        <div v-for="entry in logSearchResults" :key="`${entry.created}-${entry.funcName}-${entry.lineno}`" class="log-entry log-entry-large">
          <div class="log-entry-head">
            <el-tag size="small" :type="levelTagType(entry.level)">{{ entry.level }}</el-tag>
            <span>{{ entry.timestamp }}</span>
            <span>{{ entry.logger }}</span>
            <span>{{ entry.funcName }}:{{ entry.lineno }}</span>
          </div>
          <pre>{{ entry.formatted || entry.message }}</pre>
        </div>
      </div>
    </section>

    <section v-else-if="currentView === 'about'" class="tool-page-view about-page-view">
      <div class="log-system-head">
        <div>
          <p class="eyebrow">About</p>
          <h2>关于我们</h2>
          <p>DPU Mock API 操作台用于统一管理测试账号、会话上下文、DPU 状态模拟、日志检索和问题协作。</p>
        </div>
        <el-button plain :icon="Refresh" @click="backToConsole">返回控制台</el-button>
      </div>

      <el-card shadow="never" class="surface-card tool-page-card help-page-card">
        <div class="help-section help-callout">
          <h3>工具定位</h3>
          <p>DPU Mock API 操作台是面向 DPU 测试、联调和回归验证的内部控制台。它把账号注册、session 连接、workflow webhook 模拟、实时日志、历史日志检索和问题交接集中在同一个页面，减少脚本切换、手工拼请求和环境信息遗漏。</p>
          <p>页面设计以执行效率和可追溯性为优先：所有关键操作都围绕当前环境、手机号、session、merchant 和接口结果展开，便于测试人员、研发和支持同学在同一上下文中定位问题。</p>
        </div>
        <div class="help-section">
          <h3>适用场景</h3>
          <ol>
            <li>新建 SIT、UAT、REG 等环境的测试账号，并快速进入可执行 mock 的状态。</li>
            <li>在指定 session 下模拟核保、审批、PSP、电子签、放款、还款、多店铺等 DPU 业务状态。</li>
            <li>联调或回归时复现某个 webhook 节点，确认请求 URL、请求体、响应体和业务错误。</li>
            <li>排查“页面显示成功但业务状态未推进”“接口 200 但业务失败”“session 失效或环境选错”等问题。</li>
            <li>将问题现场沉淀到“联系我们”，让管理员或后续处理人能基于相同上下文继续跟进。</li>
          </ol>
        </div>
        <div class="help-section">
          <h3>标准使用流程</h3>
          <ol>
            <li>在“连接与注册”选择目标环境，输入手机号连接已有 session，或按 Journey、币种、资方代码注册新账号。</li>
            <li>确认右侧“当前会话”中的环境、手机号、Merchant 等信息，避免跨环境或跨账号误操作。</li>
            <li>进入“Mock 操作面板”，选择需要推进的业务节点，填写金额、状态、失败原因或 state 等参数。</li>
            <li>执行后查看当前步骤下方的返回结果，同时观察“实时日志”和“操作轨迹”确认请求已被记录。</li>
            <li>如果结果异常，进入“日志系统”按关键字、时间范围或 session 过滤日志，定位接口链路和具体错误。</li>
            <li>需要交接时，在“联系我们”记录现象、预期、复现步骤、手机号、session、关键日志和截图线索。</li>
          </ol>
        </div>
        <div class="help-section">
          <h3>核心模块能力</h3>
          <dl>
            <dt>连接与注册</dt>
            <dd>用于创建或连接测试账号上下文。注册支持 Journey、币种、资方代码和线上/线下模式选择；连接成功后会建立 session，后续 mock 操作都会绑定这个上下文。</dd>
            <dt>Mock 操作面板</dt>
            <dd>集中触发 DPU 关键业务节点，包括 SP/3PL 关联、核保、审批、PSP started/completed、电子签、放款、还款、系统事件和 Abandon。每个操作保留独立参数区，降低误填风险。</dd>
            <dt>日志系统</dt>
            <dd>用于检索后端调用日志，重点查看请求方法、URL、请求体、响应体、状态码、traceId、业务错误和异常堆栈。适合确认“接口是否真的发出”和“后端实际返回什么”。</dd>
            <dt>AI 助手</dt>
            <dd>用于辅助分析当前 session、日志和 mock 结果，也可以帮助整理 SQL、接口现象和排查思路。AI 输出只作为诊断辅助，关键业务结论仍应以接口返回、日志和数据库状态为准。</dd>
            <dt>联系我们</dt>
            <dd>用于异步交接问题现场。建议写清楚环境、手机号、session、已执行步骤、预期状态、实际状态、错误日志和截图信息，方便管理员或后续处理人快速接手。</dd>
            <dt>管理员登录</dt>
            <dd>管理员入口已调整为“回复问题”，用于集中查看和回复已提交的问题，适合团队内部维护待处理事项、补充处理结论和保留协作记录。</dd>
          </dl>
        </div>
        <div class="help-section">
          <h3>数据与安全边界</h3>
          <dl>
            <dt>环境隔离</dt>
            <dd>执行前必须确认当前环境。SIT、UAT、REG、DEV、PREPROD 的数据和网关地址不同，跨环境使用手机号或 session 会导致误判。</dd>
            <dt>测试数据</dt>
            <dd>本工具面向测试和联调用例，不应输入真实客户敏感信息。需要生产或迁移相关操作时，应按专项流程和授权要求执行。</dd>
            <dt>结果判定</dt>
            <dd>按钮执行成功只代表接口调用完成，不等同于完整业务链路成功。关键节点应结合返回体、实时日志、历史日志和必要的数据库状态共同确认。</dd>
            <dt>审计线索</dt>
            <dd>操作轨迹和日志用于辅助追溯，但不替代正式测试报告。重要验证结论仍应沉淀到 MeterSphere、缺陷单或版本验证记录中。</dd>
          </dl>
        </div>
        <div class="help-section">
          <h3>协作建议</h3>
          <dl>
            <dt>复现问题</dt>
            <dd>先固定环境、手机号、session 和执行时间窗口，再描述失败节点。不要只写“失败了”，应说明停在哪一步、期望推进到哪一步。</dd>
            <dt>提交信息</dt>
            <dd>优先提供可直接排查的信息：环境、手机号、session_id、merchant_id、接口名称、请求时间、traceId、关键响应体和截图。</dd>
            <dt>处理结论</dt>
            <dd>管理员回复时建议包含原因判断、已采取动作、是否需要重试、是否需要研发介入，以及后续验证标准。</dd>
          </dl>
        </div>
      </el-card>
    </section>

    <section v-else-if="currentView === 'contact'" class="tool-page-view contact-page-view">
      <div class="log-system-head">
        <div>
          <p class="eyebrow">Ask Us</p>
          <h2>联系我们</h2>
          <p>把问题现场、期望结果和关键信息整理清楚，管理员会统一处理。</p>
        </div>
        <el-button plain :icon="Refresh" @click="backToConsole">返回控制台</el-button>
      </div>

      <div class="contact-overview-grid">
        <div class="contact-stat-card">
          <span>问题总数</span>
          <strong>{{ contactIssues.length }}</strong>
          <p>当前浏览器已记录的问题总量</p>
        </div>
        <div class="contact-stat-card">
          <span>待回复</span>
          <strong>{{ pendingContactIssuesCount }}</strong>
          <p>需要管理员继续处理的问题</p>
        </div>
        <div class="contact-stat-card">
          <span>已回复</span>
          <strong>{{ repliedContactIssuesCount }}</strong>
          <p>已完成答复的问题</p>
        </div>
      </div>

      <div class="contact-page-stack">
        <el-card shadow="never" class="surface-card contact-admin-card">
          <template #header>
            <div class="card-head">
              <div class="head-copy">
                <h3>提交问题</h3>
                <p>建议按“现象 + 预期 + 复现步骤 + 关键上下文”来写。</p>
              </div>
            </div>
          </template>

          <div class="contact-context">
            <div><span>环境</span><strong>{{ sessionSummary?.env || connectionForm.env }}</strong></div>
            <div><span>手机号</span><strong>{{ sessionSummary?.phone_number || connectionForm.phone_number || '-' }}</strong></div>
            <div><span>Session</span><strong>{{ activeSessionId || '-' }}</strong></div>
          </div>

          <el-form label-position="top" class="tight-form contact-question-form">
            <el-form-item label="问题描述">
              <el-input
                v-model="contactForm.issue"
                type="textarea"
                :rows="8"
                placeholder="例如：reg 环境下已执行审批和 PSP started，但没有推进到 eSign。期望继续到签约完成。手机号 / session / 报错如下..."
              />
            </el-form-item>
            <el-button type="primary" :icon="Position" @click="submitContactIssue">提交问题</el-button>
          </el-form>
        </el-card>

        <el-card shadow="never" class="surface-card contact-admin-card">
          <template #header>
            <div class="card-head">
              <div class="head-copy">
                <h3>问题记录</h3>
                <p>按最新提交时间倒序展示，已回复内容会保留在对应问题下方。</p>
              </div>
              <el-tag type="info" effect="plain">{{ contactIssues.length }} 条</el-tag>
            </div>
          </template>

          <section class="contact-issue-list">
            <div v-if="contactIssues.length === 0" class="contact-empty">还没有提交的问题。</div>
            <article v-for="item in contactIssues" :key="item.id" class="contact-issue-item">
              <div class="contact-issue-head">
                <el-tag :type="item.status === '已回复' ? 'success' : 'warning'" effect="plain">{{ item.status }}</el-tag>
                <span>{{ item.created_at }}</span>
              </div>
              <p class="contact-issue-text">{{ item.issue }}</p>
              <div class="contact-issue-meta">
                <span>{{ item.env }}</span>
                <span>{{ item.phone_number }}</span>
                <span>{{ item.session_id }}</span>
              </div>
              <div v-if="item.reply" class="contact-reply-result">
                <span>回复 {{ item.replied_at }}</span>
                <p>{{ item.reply }}</p>
              </div>
            </article>
          </section>
        </el-card>
      </div>
    </section>

    <section v-else-if="currentView === 'ai'" class="ai-page-view">
      <div class="ai-page-shell">
        <main class="ai-conversation-panel">
          <div class="ai-conversation-head">
            <div>
              <p class="eyebrow">DPU Chat</p>
              <h2>AI 助手</h2>
              <p>像聊天一样提问，也可以直接执行只读 SQL、查询 merchant、分析最近日志和当前 session。</p>
            </div>
            <div class="ai-conversation-actions">
              <el-select v-model="aiExecutionEnv" class="ai-exec-select" aria-label="AI 执行环境">
                <el-option
                  v-for="env in aiSqlDataSources"
                    :key="`ai-${env}`"
                    :label="env"
                    :value="env"
                />
              </el-select>
              <el-tag size="large" :type="aiSending ? 'warning' : 'success'">{{ aiSending ? '处理中' : '就绪' }}</el-tag>
              <el-button :icon="Delete" plain @click="clearAiChat">清空对话</el-button>
              <el-button plain :icon="Refresh" @click="backToConsole">返回控制台</el-button>
            </div>
          </div>

          <div class="ai-context-strip">
            <div><span>Session</span><strong>{{ activeSessionId || '-' }}</strong></div>
            <div><span>环境</span><strong>{{ sessionSummary?.env || connectionForm.env }}</strong></div>
            <div><span>手机号</span><strong>{{ sessionSummary?.phone_number || connectionForm.phone_number || '-' }}</strong></div>
            <div><span>Merchant</span><strong>{{ sessionSummary?.merchant_id || '-' }}</strong></div>
            <div><span>实时日志</span><strong>{{ logStatusText }}</strong></div>
          </div>

          <div v-if="aiMessages.length === 0" class="ai-empty-state">
            <p>可以直接问业务问题，也可以粘贴 SQL。比如“帮我看当前 session 为什么没推进到 eSign”，或者直接输入一条 SELECT。</p>
            <p>助手会带上当前环境、Session、手机号、Merchant 和最近日志上下文；需要切换查询环境时，直接改上方环境选择。</p>
            <div class="ai-prompt-grid">
              <button v-for="prompt in aiQuickPrompts" :key="prompt" type="button" @click="useAiPrompt(prompt)">
                {{ prompt }}
              </button>
            </div>
          </div>

          <div class="ai-chat-body ai-page-chat-body">
            <div v-for="message in aiMessages" :key="message.id" class="chat-message" :class="message.role">
              <div class="chat-meta">
                <strong>{{ message.role === 'user' ? '你' : '助手' }}</strong>
                <span>{{ message.at }}</span>
              </div>
              <div class="chat-bubble">{{ message.content }}</div>
              <details v-if="message.meta?.tool_result" class="chat-detail">
                <summary>工具结果</summary>
                <pre>{{ JSON.stringify(message.meta.tool_result, null, 2) }}</pre>
              </details>
            </div>
          </div>

          <div v-if="aiError" class="chat-error">{{ aiError }}</div>

          <div class="ai-page-input">
            <el-input
              v-model="aiInput"
              type="textarea"
              :rows="5"
              placeholder="问 DPU 问题、让它分析日志，或直接输入 SQL，例如：select merchant_id from dpu_users where phone_number='...'"
              @keydown.enter.exact.prevent="handleAiSend"
            />
            <div class="ai-chat-actions">
              <el-button :icon="ChatDotRound" @click="clearAiChat">重置</el-button>
              <el-button type="primary" :icon="Position" :loading="aiSending" @click="handleAiSend">发送</el-button>
            </div>
          </div>
        </main>
      </div>
    </section>

    <section v-else-if="currentView === 'contactAdmin'" class="tool-page-view contact-admin-view">
      <div class="log-system-head">
        <div>
          <p class="eyebrow">Admin</p>
          <h2>回复问题</h2>
          <p>管理员在这里统一回复“联系我们”提交的问题。</p>
        </div>
        <el-button plain :icon="Refresh" @click="backToConsole">返回控制台</el-button>
      </div>

      <div class="contact-admin-grid">
        <el-card shadow="never" class="surface-card contact-admin-card">
          <template #header>
            <div class="card-head">
              <div class="head-copy">
                <h3>回复问题</h3>
                <p>先填写回复内容，再在右侧选择一个待处理问题。</p>
              </div>
              <el-tag type="success" effect="plain">{{ authDisplayName }} 已登录</el-tag>
            </div>
          </template>

          <div class="contact-reply-box">
            <el-input
              v-model="contactAdminForm.reply"
              type="textarea"
              :rows="5"
              placeholder="输入回复内容，然后在右侧选择一个待回复问题。"
            />
            <el-button :icon="SwitchButton" text @click="handleLogout">退出登录</el-button>
          </div>

          <p v-if="contactAdminError" class="contact-error">{{ contactAdminError }}</p>
        </el-card>

        <el-card shadow="never" class="surface-card contact-admin-card">
          <template #header>
            <div class="card-head">
              <div class="head-copy">
                <h3>待处理问题</h3>
                <p>这里只显示未回复的问题；回复后会回显到“联系我们”的问题记录里。</p>
              </div>
              <el-tag type="info" effect="plain">{{ pendingContactIssues.length }} 条</el-tag>
            </div>
          </template>

          <section class="contact-issue-list contact-issue-list-admin">
            <div v-if="pendingContactIssues.length === 0" class="contact-empty">暂无待处理问题。</div>
            <article v-for="item in pendingContactIssues" :key="item.id" class="contact-issue-item">
              <div class="contact-issue-head">
                <div class="contact-issue-state">
                  <el-tag :type="item.status === '已回复' ? 'success' : 'warning'" effect="plain">{{ item.status }}</el-tag>
                  <span>{{ item.created_at }}</span>
                </div>
                <el-button
                  type="danger"
                  plain
                  :icon="Delete"
                  @click="deleteContactIssue(item.id)"
                >删除</el-button>
              </div>
              <p class="contact-issue-text">{{ item.issue }}</p>
              <div class="contact-issue-meta">
                <span>{{ item.env }}</span>
                <span>{{ item.phone_number }}</span>
                <span>{{ item.session_id }}</span>
              </div>
              <div v-if="item.reply" class="contact-reply-result">
                <span>回复 {{ item.replied_at }}</span>
                <p>{{ item.reply }}</p>
              </div>
              <el-button
                type="primary"
                plain
                :icon="ChatLineRound"
                @click="replyContactIssue(item)"
              >回复该问题</el-button>
            </article>
          </section>
        </el-card>
      </div>
    </section>

    <section v-else class="workspace-grid">
      <div class="main-column">
        <el-card shadow="never" class="surface-card">
          <template #header>
            <div class="card-head">
              <div class="head-copy">
                <h2>连接与注册</h2>
                <p>先建立 session，再执行 mock 操作。</p>
              </div>
              <el-space>
                <el-button :icon="Refresh" plain :loading="loadingHealth || loadingSessions" @click="loadSessions(); refreshHealth()">
                  刷新状态
                </el-button>
                <el-button :icon="Delete" type="danger" plain :disabled="!activeSessionId" :loading="disconnecting" @click="handleDisconnect">
                  断开会话
                </el-button>
              </el-space>
            </div>
          </template>

          <div class="dual-panel">
            <div class="form-block">
              <h3><el-icon><Connection /></el-icon> 会话连接</h3>
              <el-form label-position="top" class="tight-form">
                <el-form-item label="环境">
                  <el-select v-model="connectionForm.env">
                    <el-option
                      v-for="env in enumOptions?.environments ?? defaultEnvironments"
                      :key="env"
                      :label="env"
                      :value="env"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="手机号">
                  <el-input v-model.trim="connectionForm.phone_number" placeholder="8位或11位数字" />
                </el-form-item>
                <el-button type="primary" :icon="Connection" :loading="connecting" @click="handleConnect">
                  连接 session
                </el-button>
              </el-form>
            </div>

            <div class="form-block">
              <h3><el-icon><Document /></el-icon> 新账号注册</h3>
              <el-form label-position="top" class="tight-form">
                <el-form-item label="环境">
                  <el-select v-model="registerForm.env">
                    <el-option
                      v-for="env in enumOptions?.environments ?? defaultEnvironments"
                      :key="`reg-${env}`"
                      :label="env"
                      :value="env"
                    />
                  </el-select>
                </el-form-item>
                <div class="form-row register-fields" :class="{ 'is-offline': registerForm.offline }">
                  <el-form-item v-if="!registerForm.offline" label="Journey">
                    <el-select v-model="registerForm.journey">
                      <el-option
                        v-for="journey in enumOptions?.journeys ?? defaultJourneys"
                        :key="journey"
                        :label="journeyLabel(journey)"
                        :value="journey"
                      />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="币种" :class="{ 'full-row': registerForm.offline }">
                    <el-select v-model="registerForm.currency">
                      <el-option
                        v-for="currency in enumOptions?.currencies ?? defaultCurrencies"
                        :key="currency"
                        :label="currency"
                        :value="currency"
                      />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="资方代码" class="full-row">
                    <el-select v-model="registerForm.funder_resource">
                      <el-option
                        v-for="funderResource in enumOptions?.funder_resources ?? defaultFunderResources"
                        :key="funderResource"
                        :label="funderResource"
                        :value="funderResource"
                      />
                    </el-select>
                  </el-form-item>
                </div>
                <el-form-item>
                  <el-switch v-model="registerForm.offline" active-text="线下模式" inactive-text="线上模式" />
                </el-form-item>
                <div class="register-actions">
                  <el-button type="success" :icon="Promotion" :loading="registering" @click="handleRegister">
                    执行注册
                  </el-button>
                  <el-button
                    type="warning"
                    plain
                    :icon="Connection"
                    :loading="registeringAndBinding"
                    @click="handleRegisterAndRunMultiShop"
                  >
                    注册并完成绑店
                  </el-button>
                </div>
              </el-form>
            </div>
          </div>

        </el-card>

        <el-card shadow="never" class="surface-card">
          <template #header>
            <div class="card-head">
              <div class="head-copy">
                <h2>Mock 操作面板</h2>
                <p>按当前 session 执行 webhook 模拟操作，执行结果会保留在对应步骤下方。</p>
              </div>
              <el-tag :type="activeSessionId ? 'success' : 'warning'" size="large">
                {{ activeSessionId ? `session: ${activeSessionId.slice(0, 8)}...` : '未连接 session' }}
              </el-tag>
            </div>
          </template>

          <div class="operation-context">
            <div>
              <span>环境</span>
              <strong>{{ sessionSummary?.env || connectionForm.env }}</strong>
            </div>
            <div>
              <span>手机号</span>
              <strong>{{ sessionSummary?.phone_number || connectionForm.phone_number || '-' }}</strong>
            </div>
            <div>
              <span>Merchant ID</span>
              <strong>{{ sessionSummary?.merchant_id || '-' }}</strong>
            </div>
          </div>

          <div v-if="sessionSummary" class="application-selector">
            <span class="application-selector-label">申请单</span>
            <div class="application-selector-current">
              <div>
                <span>Application</span>
                <strong>{{ selectedApplicationUniqueId || sessionSummary?.application_unique_id || '-' }}</strong>
              </div>
              <div>
                <span>Currency</span>
                <strong>{{ selectedApplicationCurrency }}</strong>
              </div>
              <div>
                <span>Lender</span>
                <strong>{{ selectedApplication?.lender_code || sessionSummary?.lender_code || '-' }}</strong>
              </div>
              <div>
                <span>Status</span>
                <strong>{{ selectedApplication?.application_status || sessionSummary?.application_status || '-' }}</strong>
              </div>
            </div>
            <el-select
              v-if="applicationOptions.length > 1"
              v-model="selectedApplicationUniqueId"
              filterable
              class="application-select"
            >
              <el-option
                v-for="application in applicationOptions"
                :key="application.application_unique_id"
                :label="application.application_unique_id"
                :value="application.application_unique_id"
              >
                <div class="application-option">
                  <strong>{{ application.application_unique_id }}</strong>
                  <span>{{ application.finance_product_currency || selectedApplicationCurrency }}</span>
                  <span>{{ application.application_status || '-' }}</span>
                  <span>{{ application.lender_code || '-' }}</span>
                </div>
              </el-option>
            </el-select>
            <span v-else class="application-single-note">默认最新申请单</span>
          </div>

          <div class="operation-panels operation-button-list">
            <div
              v-for="operation in operations"
              :key="operation.key"
              class="operation-row"
              :class="{ active: activeOperationKey === operation.key }"
            >
              <button
                type="button"
                class="operation-toggle"
                :aria-expanded="activeOperationKey === operation.key"
                @click="toggleOperationPanel(operation.key)"
              >
                <span class="operation-toggle-main">
                  <el-icon><component :is="operation.icon" /></el-icon>
                  <span>{{ operation.title }}</span>
                </span>
                <span class="operation-toggle-meta">
                  <code>{{ operation.endpoint }}</code>
                  <el-icon><component :is="activeOperationKey === operation.key ? ArrowDown : ArrowRight" /></el-icon>
                </span>
              </button>
            </div>
          </div>

          <div v-if="activeOperation" class="operation-detail-dock">
            <div class="operation-detail-head">
              <div>
                <p>{{ activeOperation.title }}</p>
                <span>{{ activeOperation.description }}</span>
              </div>
              <el-button size="small" text @click="toggleOperationPanel(activeOperation.key)">
                收起
              </el-button>
            </div>
            <div class="operation-body">
              <code class="endpoint-chip">{{ activeOperation.endpoint }}</code>
              <el-form label-position="top" class="tight-form">
                <div v-if="shouldShowPspAuthorizationRows" class="psp-status-panel">
                  <div class="psp-status-head">
                    <span>店铺授权状态</span>
                    <el-button size="small" text :loading="loadingPspAuthorizationRows" @click="loadPspAuthorizationRows">
                      刷新
                    </el-button>
                  </div>
                  <div class="psp-status-table">
                    <div class="psp-status-row psp-status-header">
                      <span>merchant_account_id</span>
                      <span>SP authorization_id</span>
                      <span>SP 状态</span>
                      <span>3P 状态</span>
                      <span>PSP 状态</span>
                      <span>选择</span>
                    </div>
                    <div v-if="!loadingPspAuthorizationRows && pspAuthorizationRows.length === 0" class="psp-status-empty">
                      暂无店铺授权记录。
                    </div>
                    <div
                      v-for="row in pspAuthorizationRows"
                      :key="row.merchant_account_id"
                      class="psp-status-row"
                      :class="{ selected: row.merchant_account_id === selectedPspMerchantAccountId }"
                    >
                      <strong>{{ row.merchant_account_id || '-' }}</strong>
                      <strong>{{ row.sp_authorization_id || '-' }}</strong>
                      <span>{{ row.sp_status || '-' }}</span>
                      <span>{{ row.three_pl_status || '-' }}</span>
                      <span>{{ row.psp_status || '-' }}</span>
                      <el-button
                        size="small"
                        :type="row.merchant_account_id === selectedPspMerchantAccountId ? 'primary' : 'default'"
                        :disabled="!isPspRowSelectable(row)"
                        @click="selectPspAuthorizationRow(row)"
                      >
                        {{ row.merchant_account_id === selectedPspMerchantAccountId ? '已选中' : '选择' }}
                      </el-button>
                    </div>
                  </div>
                </div>

                <div v-if="shouldShowDowsureMerchantAccounts" class="dowsure-accounts-panel">
                  <div class="psp-status-head">
                    <span>DOWSURE 店铺额度</span>
                    <el-button size="small" text :loading="loadingDowsureMerchantAccounts" @click="loadDowsureMerchantAccounts">
                      刷新
                    </el-button>
                  </div>
                  <div class="dowsure-accounts-table">
                    <div class="dowsure-accounts-row dowsure-accounts-header">
                      <span>merchant_account_id</span>
                      <span>SP authorization_id</span>
                      <span>created_at</span>
                      <span>merchantAccountLimit</span>
                    </div>
                    <div v-if="!loadingDowsureMerchantAccounts && operationForms.underwrittenDowsure.merchant_accounts.length === 0" class="psp-status-empty">
                      暂无 DOWSURE 店铺记录。
                    </div>
                    <div
                      v-for="row in operationForms.underwrittenDowsure.merchant_accounts"
                      :key="row.merchantAccountId"
                      class="dowsure-accounts-row"
                    >
                      <strong>{{ row.merchant_account_id || '-' }}</strong>
                      <strong>{{ row.merchantAccountId || '-' }}</strong>
                      <span>{{ row.created_at || '-' }}</span>
                      <el-input-number
                        v-model="row.merchantAccountLimit"
                        :min="0"
                        :step="1000"
                        controls-position="right"
                        class="full-width"
                      />
                    </div>
                  </div>
                </div>

                <div class="operation-fields" :class="{ empty: activeOperation.fields.length === 0 }">
                  <template v-if="activeOperation.fields.length">
                    <template v-for="field in activeOperation.fields" :key="`${activeOperation.key}-${field.prop}`">
                      <el-form-item v-if="!field.visible || field.visible(operationForms[activeOperation.key])" :label="field.label">
                        <el-input
                          v-if="field.type === 'text'"
                          v-model="operationForms[activeOperation.key][field.prop]"
                          :placeholder="field.placeholder"
                        />
                        <el-input-number
                          v-else-if="field.type === 'number'"
                          v-model="operationForms[activeOperation.key][field.prop]"
                          :min="field.min"
                          :step="field.step || 1"
                          controls-position="right"
                          class="full-width"
                        />
                        <el-select v-else-if="field.type === 'select'" v-model="operationForms[activeOperation.key][field.prop]">
                          <el-option
                            v-for="option in fieldOptions(field)"
                            :key="`${field.prop}-${option.value}`"
                            :label="option.label"
                            :value="option.value"
                          />
                        </el-select>
                      </el-form-item>
                    </template>
                  </template>
                  <div v-else class="no-params">这个操作不需要额外参数。</div>
                </div>

                <el-button
                  type="primary"
                  :disabled="!activeSessionId"
                  :loading="runningOperationKey === activeOperation.key"
                  @click="handleOperationRun(activeOperation)"
                >
                  执行 {{ activeOperation.title }}
                </el-button>
              </el-form>

              <div
                v-if="operationResults[activeOperation.key]"
                class="result-strip"
                :class="{ 'result-strip-error': operationResults[activeOperation.key]?.success === false }"
              >
                <span class="result-title">最近一次执行结果</span>
                <pre>{{ JSON.stringify(operationResults[activeOperation.key], null, 2) }}</pre>
              </div>
            </div>
          </div>
        </el-card>
      </div>

      <aside class="side-column">
        <el-card shadow="never" class="surface-card">
          <template #header>
            <div class="card-head">
              <div class="head-copy">
                <h2>当前会话</h2>
                <p>活动连接与最近状态。</p>
              </div>
            </div>
          </template>

          <div v-if="sessionSummary" class="session-summary">
            <div class="summary-row"><span>Session ID</span><strong>{{ sessionSummary.session_id }}</strong></div>
            <div class="summary-row"><span>环境</span><strong>{{ sessionSummary.env }}</strong></div>
            <div class="summary-row"><span>手机号</span><strong>{{ sessionSummary.phone_number }}</strong></div>
            <div class="summary-row"><span>Merchant</span><strong>{{ sessionSummary.merchant_id || '-' }}</strong></div>
            <div class="summary-row"><span>选中申请单</span><strong>{{ selectedApplicationUniqueId || '-' }}</strong></div>
            <div class="summary-row"><span>申请单数量</span><strong>{{ applicationOptions.length }}</strong></div>
          </div>
          <el-empty v-else description="还没有活跃会话" />
        </el-card>

        <el-card shadow="never" class="surface-card">
          <template #header>
            <div class="card-head">
              <div class="head-copy">
                <h2>操作轨迹</h2>
                <p>前端侧最近行为记录。</p>
              </div>
            </div>
          </template>

          <div class="activity-list">
            <div v-if="activityFeed.length === 0" class="activity-empty">还没有操作记录。</div>
            <div v-for="item in activityFeed" :key="item.id" class="activity-item">
              <div class="activity-head">
                <el-tag size="small" effect="dark">{{ item.kind }}</el-tag>
                <span>{{ item.at }}</span>
              </div>
              <strong>{{ item.title }}</strong>
              <pre>{{ JSON.stringify(item.payload, null, 2) }}</pre>
            </div>
          </div>
        </el-card>
      </aside>
    </section>

    </template>

    <el-drawer
      v-model="scenarioHistoryDetailVisible"
      size="58%"
      class="scenario-history-drawer"
      title="执行详情"
    >
      <section v-if="selectedScenarioHistoryRecord" class="scenario-history-detail">
        <div class="scenario-detail-header">
          <div>
            <span>场景</span>
            <strong>{{ selectedScenarioHistoryRecord.scenario }}</strong>
          </div>
          <div>
            <span>状态</span>
            <el-tag :type="selectedScenarioHistoryRecord.status === '完成' ? 'success' : selectedScenarioHistoryRecord.status === '未执行' ? 'warning' : 'danger'" effect="plain">
              {{ selectedScenarioHistoryRecord.status }}
            </el-tag>
          </div>
          <div>
            <span>环境</span>
            <strong>{{ selectedScenarioHistoryRecord.env }}</strong>
          </div>
          <div>
            <span>耗时</span>
            <strong>{{ selectedScenarioHistoryRecord.duration }}</strong>
          </div>
        </div>

        <div v-if="selectedScenarioHistoryRecord.context" class="scenario-detail-context">
          <div><span>手机号</span><strong>{{ selectedScenarioHistoryRecord.context.phone_number || '-' }}</strong></div>
          <div><span>Merchant ID</span><strong>{{ selectedScenarioHistoryRecord.context.merchant_id || '-' }}</strong></div>
          <div><span>Application Unique ID</span><strong>{{ selectedScenarioHistoryRecord.context.application_unique_id || '-' }}</strong></div>
        </div>

        <div class="scenario-detail-step-list">
          <article
            v-for="step in selectedScenarioHistoryRecord.steps || []"
            :key="`${selectedScenarioHistoryRecord.id}-${step.key}`"
            class="scenario-detail-step"
          >
            <div class="scenario-detail-step-head">
              <span class="step-index">{{ step.order }}</span>
              <el-tag
                size="small"
                :type="step.status === 'success' ? 'success' : step.status === 'skipped' ? 'info' : step.status === 'idle' ? 'warning' : 'danger'"
                effect="plain"
              >
                {{ step.status === 'success' ? '成功' : step.status === 'skipped' ? '跳过' : step.status === 'idle' ? '未执行' : '失败' }}
              </el-tag>
              <strong>{{ step.title }}</strong>
              <code>{{ step.endpoint }}</code>
            </div>
            <p v-if="step.error_message" class="scenario-detail-error">{{ step.error_message }}</p>
            <div class="scenario-detail-payload-grid">
              <div class="response-block">
                <div class="response-block-head">
                  <strong>Request</strong>
                  <el-tag size="small" effect="plain">{{ step.method || 'POST' }}</el-tag>
                </div>
                <pre>{{ JSON.stringify(step.request, null, 2) }}</pre>
              </div>
              <div class="response-block">
                <div class="response-block-head">
                  <strong>Response</strong>
                  <el-tag size="small" effect="plain">{{ step.status }}</el-tag>
                </div>
                <pre>{{ JSON.stringify(step.response, null, 2) }}</pre>
              </div>
            </div>
          </article>
        </div>
      </section>
    </el-drawer>
  </div>
</template>



