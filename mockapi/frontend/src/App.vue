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
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import {
  connectSession,
  disconnectSession,
  fetchEnums,
  fetchHealth,
  fetchLogs,
  fetchSessions,
  registerAccount,
  registerAndRunMultiShop,
  runMockOperation,
  sendAiChat,
} from './api.js'

const defaultEnvironments = ['sit', 'uat', 'dev', 'preprod', 'reg', 'local']
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

const logSearchForm = reactive({
  keyword: '',
  timeRange: [],
  limit: 500,
})

const contactIssuesStorageKey = 'mockapi-contact-issues'
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

const reasonOptions = computed(() => enumOptions.value?.returned_failure_reasons ?? [])
const approvedRejectionOptions = computed(() => enumOptions.value?.approved_rejection_reasons ?? [])
const drawdownReasonOptions = computed(() => enumOptions.value?.drawdown_failure_reasons ?? [])
const repaymentReasonOptions = computed(() => enumOptions.value?.repayment_failure_reasons ?? [])
const spFailureOptions = computed(() => enumOptions.value?.sp_update_failure_reasons ?? [])
const applicationAbandonOptions = computed(() => enumOptions.value?.application_abandon_reasons ?? [])
const pendingContactIssuesCount = computed(() => contactIssues.value.filter((item) => item.status !== '已回复').length)
const repliedContactIssuesCount = computed(() => contactIssues.value.filter((item) => item.status === '已回复').length)
const pendingContactIssues = computed(() => contactIssues.value.filter((item) => item.status !== '已回复'))
const activeToolModule = computed(() => {
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
  return activityFeed.value.find((item) => item.kind === 'connect')?.payload ?? null
})

const activeOperation = computed(() => (
  operations.value.find((item) => item.key === activeOperationKey.value) ?? null
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

const aiQuickPrompts = [
  '帮我看一下当前 session 的状态，哪些关键信息还缺失？',
  '查询当前手机号对应的 merchant_id',
  '根据最近日志分析失败原因，并告诉我下一步怎么查',
  'SELECT merchant_id, phone_number FROM dpu_users ORDER BY created_at DESC LIMIT 5',
]

watch(
  () => connectionForm.env,
  (value) => {
    registerForm.env = value
  },
)

watch(darkMode, (value) => {
  document.documentElement.classList.toggle('mockapi-dark', value)
  window.localStorage.setItem('mockapi-theme', value ? 'dark' : 'light')
}, { immediate: true })

onMounted(async () => {
  const savedTheme = window.localStorage.getItem('mockapi-theme')
  if (savedTheme) {
    darkMode.value = savedTheme === 'dark'
  } else {
    darkMode.value = window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
  }
  loadContactIssues()
  await Promise.all([refreshHealth(), loadEnums(), loadSessions()])
})

onBeforeUnmount(() => {
  closeSocket()
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
    liveSessions.value = await fetchSessions()
  } catch (error) {
    pushActivity('error', '刷新会话列表失败', normalizeError(error))
  } finally {
    loadingSessions.value = false
  }
}

async function handleConnect() {
  connecting.value = true
  try {
    await establishSession({ ...connectionForm }, '会话连接成功')
  } catch (error) {
    pushActivity('error', '会话连接失败', normalizeError(error))
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
    registerResult.value = await registerAccount({ ...registerForm })
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

async function handleOperationRun(operation) {
  if (!activeSessionId.value) {
    pushActivity('error', '请先连接会话', '当前没有 session_id，无法执行 mock 操作。')
    return
  }

  runningOperationKey.value = operation.key
  try {
    const data = await runMockOperation(operation.endpoint, buildPayload(operation))
    operationResults[operation.key] = data
    pushActivity('mock', `${operation.title} 已执行`, data)
  } catch (error) {
    pushActivity('error', `${operation.title} 执行失败`, normalizeError(error))
  } finally {
    runningOperationKey.value = ''
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
    const response = await sendAiChat({
      message: text,
      history: aiMessages.value
        .filter((item) => ['user', 'assistant', 'tool'].includes(item.role))
        .slice(-12)
        .map((item) => ({ role: item.role, content: item.content })),
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
  const payload = { session_id: activeSessionId.value }
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

function openLogSystem() {
  closeToolRail()
  currentView.value = 'logs'
  runLogSearch()
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
  aiExecutionEnv.value = sessionSummary.value?.env || connectionForm.env || registerForm.env || 'sit'
  currentView.value = 'ai'
}

function useAiPrompt(prompt) {
  aiInput.value = prompt
}

function submitContactIssue() {
  const issue = contactForm.issue.trim()
  if (!issue) {
    pushActivity('contact', '问题内容为空', '请先输入需要反馈的问题。')
    return
  }
  const contactIssue = {
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    issue,
    env: sessionSummary.value?.env || connectionForm.env,
    phone_number: sessionSummary.value?.phone_number || connectionForm.phone_number || '-',
    session_id: activeSessionId.value || '-',
    status: '待回复',
    reply: '',
    created_at: new Date().toLocaleString(),
    replied_at: '',
  }
  contactIssues.value.unshift(contactIssue)
  persistContactIssues()
  pushActivity('contact', '已留下问题', contactIssue)
  contactForm.issue = ''
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

function replyContactIssue(issue) {
  const reply = contactAdminForm.reply.trim()
  if (!reply) {
    contactAdminError.value = '请先填写回复内容'
    return
  }
  issue.reply = reply
  issue.status = '已回复'
  issue.replied_at = new Date().toLocaleString()
  persistContactIssues()
  contactAdminForm.reply = ''
  contactAdminError.value = ''
  pushActivity('contact', '已回复联系我们问题', {
    issue_id: issue.id,
    reply,
  })
}

function deleteContactIssue(issueId) {
  const target = contactIssues.value.find((item) => item.id === issueId)
  if (!target) return
  const confirmed = window.confirm('确认删除这个问题吗？删除后不会再展示在问题记录里。')
  if (!confirmed) return
  contactIssues.value = contactIssues.value.filter((item) => item.id !== issueId)
  persistContactIssues()
  contactAdminError.value = ''
  pushActivity('contact', '已删除联系我们问题', {
    issue_id: issueId,
    status: target.status,
  })
}

function loadContactIssues() {
  const raw = window.localStorage.getItem(contactIssuesStorageKey)
  if (!raw) return
  try {
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed)) {
      contactIssues.value = parsed.filter((item) => item && item.id && item.issue)
    }
  } catch (error) {
    console.warn('Failed to load contact issues', error)
  }
}

function persistContactIssues() {
  window.localStorage.setItem(contactIssuesStorageKey, JSON.stringify(contactIssues.value))
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
  const data = await connectSession(payload)
  activeSessionId.value = data.session_id
  pushActivity('connect', title, data)
  await loadSessions()
  connectLogs(data.session_id)
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
      <button class="side-tool-action" :class="{ active: activeToolModule === 'logs' }" type="button" @click="openLogSystem">
        <el-icon><Monitor /></el-icon>
        <span>日志系统</span>
      </button>
      <button class="side-tool-action" :class="{ active: activeToolModule === 'ai' }" type="button" @click="openAiPage">
        <el-icon><ChatLineRound /></el-icon>
        <span>AI 助手</span>
      </button>
      <button class="side-tool-action" :class="{ active: activeToolModule === 'about' }" type="button" @click="openAboutView">
        <el-icon><Document /></el-icon>
        <span>关于我们</span>
      </button>
      <button class="side-tool-action" :class="{ active: activeToolModule === 'contact' }" type="button" @click="openContactView">
        <el-icon><Position /></el-icon>
        <span>联系我们</span>
      </button>
      <button class="side-tool-action" :class="{ active: activeToolModule === 'contactAdmin' }" type="button" @click="openContactAdminView">
        <el-icon><Connection /></el-icon>
        <span>管理员登录</span>
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
          <button class="hero-action" :class="{ active: activeToolModule === 'logs' }" type="button" @click="openLogSystem">
            <el-icon><Monitor /></el-icon>
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
          <button class="hero-action" :class="{ active: activeToolModule === 'contactAdmin' }" type="button" @click="openContactAdminView">
            <el-icon><Connection /></el-icon>
            <span>管理员登录</span>
          </button>
        </template>
      </div>
    </section>


    <section v-if="currentView === 'logs'" class="log-system-view">
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
            <dd>用于集中查看和回复已提交的问题，适合团队内部维护待处理事项、补充处理结论和保留协作记录。</dd>
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
                  v-for="env in enumOptions?.environments ?? defaultEnvironments"
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
          <h2>管理员登录</h2>
          <p>使用 admin / admin 登录后，在这里统一回复“联系我们”提交的问题。</p>
        </div>
        <el-button plain :icon="Refresh" @click="backToConsole">返回控制台</el-button>
      </div>

      <div v-if="!contactAdminLoggedIn" class="contact-admin-login-grid">
        <el-card shadow="never" class="surface-card contact-admin-card">
          <template #header>
            <div class="card-head">
              <div class="head-copy">
                <h3>管理员登录</h3>
                <p>登录成功后才能查看待处理问题和填写回复。</p>
              </div>
              <el-tag type="warning" effect="plain">未登录</el-tag>
            </div>
          </template>

          <el-form label-position="top" class="tight-form contact-login-form" @submit.prevent="handleContactAdminLogin">
            <el-form-item label="账号">
              <el-input v-model="contactAdminForm.username" placeholder="admin" autocomplete="username" />
            </el-form-item>
            <el-form-item label="密码">
              <el-input
                v-model="contactAdminForm.password"
                placeholder="admin"
                type="password"
                autocomplete="current-password"
                show-password
                @keydown.enter.prevent="handleContactAdminLogin"
              />
            </el-form-item>
            <el-button type="primary" :icon="Connection" @click="handleContactAdminLogin">登录</el-button>
          </el-form>

          <p v-if="contactAdminError" class="contact-error">{{ contactAdminError }}</p>
        </el-card>
      </div>

      <div v-else class="contact-admin-grid">
        <el-card shadow="never" class="surface-card contact-admin-card">
          <template #header>
            <div class="card-head">
              <div class="head-copy">
                <h3>回复问题</h3>
                <p>先填写回复内容，再在右侧选择一个待处理问题。</p>
              </div>
              <el-tag type="success" effect="plain">admin 已登录</el-tag>
            </div>
          </template>

          <div class="contact-reply-box">
            <el-input
              v-model="contactAdminForm.reply"
              type="textarea"
              :rows="5"
              placeholder="输入回复内容，然后在右侧选择一个待回复问题。"
            />
            <el-button :icon="Delete" text @click="handleContactAdminLogout">退出登录</el-button>
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
              <span>实时日志</span>
              <strong>{{ logStatusText }}</strong>
            </div>
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

              <div v-if="operationResults[activeOperation.key]" class="result-strip">
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

  </div>
</template>



