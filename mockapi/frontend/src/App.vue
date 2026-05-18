<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import {
  Check,
  Connection,
  Cpu,
  Delete,
  Document,
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
import {
  connectSession,
  disconnectSession,
  fetchEnums,
  fetchHealth,
  fetchLogs,
  fetchSessions,
  registerAccount,
  runMockOperation,
  sendAiChat,
} from './api.js'

const defaultEnvironments = ['sit', 'uat', 'dev', 'preprod', 'reg', 'local']
const defaultJourneys = ['200K', '500K', '2000K']
const defaultCurrencies = ['USD', 'CNY']
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
const disconnecting = ref(false)
const loadingSessions = ref(false)
const runningOperationKey = ref('')
const enumOptions = ref(null)
const activePanels = ref([])
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
const aiDrawerOpen = ref(false)
const aiDrawerWidth = ref(420)
const aiExecutionEnv = ref('sit')
const aiMessages = ref([])
const aiInput = ref('')
const aiSending = ref(false)
const aiError = ref('')
const aiResizing = ref(false)
const currentView = ref('console')
const logSearchLoading = ref(false)
const logSearchResults = ref([])

const logSearchForm = reactive({
  keyword: '',
  timeRange: [],
  limit: 500,
})

const connectionForm = reactive({
  env: 'sit',
  phone_number: '',
})

const registerForm = reactive({
  env: 'sit',
  journey: '500K',
  currency: 'USD',
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

const sessionSummary = computed(() => {
  const current = liveSessions.value.find((item) => item.session_id === activeSessionId.value)
  if (current) return current
  return activityFeed.value.find((item) => item.kind === 'connect')?.payload ?? null
})

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
    detail: wsError.value || `${eventLogs.value.length} 条缓存日志`,
    tone: wsConnected.value ? 'success' : 'warning',
  },
])

const logStatusText = computed(() => {
  if (!activeSessionId.value) return '未连接会话'
  if (wsConnected.value) return '实时日志已连接'
  if (wsError.value) return `日志连接异常: ${wsError.value}`
  return '日志连接中'
})

const registerStatusMessage = computed(() => {
  if (!registerResult.value) return ''
  return registerAutoConnected.value
    ? '已自动连接到新注册账号，可以直接执行 mock 操作。'
    : '注册已完成，但还没有可用会话，请点击“连接 session”继续。'
})

const operations = computed(() => [
  {
    key: 'multiShopBinding',
    title: '多店铺 SP 绑定',
    icon: Link,
    endpoint: '/api/mock/multi-shop-binding',
    description: '第一步输入 state，获取 SP 授权 URL。',
    fields: [{ prop: 'state', label: 'State', type: 'text', placeholder: '请输入 state' }],
  },
  {
    key: 'spStatusUpdate',
    title: 'SP 状态更新',
    icon: Cpu,
    endpoint: '/api/mock/sp-status-update',
    description: '更新 SP 状态，可选失败原因。',
    fields: [
      { prop: 'platform_seller_id', label: 'Platform Seller ID', type: 'text', placeholder: '可空，默认使用当前 session 的值' },
      { prop: 'status', label: '状态', type: 'select', options: ['SUCCESS', 'FAIL'] },
      {
        prop: 'failure_reason_index',
        label: '失败原因',
        type: 'select',
        options: spFailureOptions.value.map((item) => ({ label: item.label, value: item.index })),
        visible: (form) => form.status === 'FAIL',
      },
    ],
  },
  {
    key: 'multiShop3plRedirect',
    title: '多店铺 3PL Redirect',
    icon: Link,
    endpoint: '/api/mock/multi-shop-3pl-redirect',
    description: '第二步生成 3PL 跳转 URL。',
    fields: [],
  },
  {
    key: 'linkSp3pl',
    title: 'SP-3PL 关联',
    icon: Link,
    endpoint: '/api/mock/link-sp-3pl',
    description: '根据当前会话手机号触发 SP 与 3PL 店铺关联。',
    fields: [],
  },
  {
    key: 'underwritten',
    title: '核保',
    icon: Document,
    endpoint: '/api/mock/underwritten',
    description: '提交核保额度和状态。',
    fields: [
      { prop: 'amount', label: '核保额度', type: 'number', min: 1, step: 1000 },
      { prop: 'status', label: '状态', type: 'select', options: enumOptions.value?.underwritten_statuses ?? [] },
    ],
  },
  {
    key: 'approvedOffer',
    title: '审批',
    icon: Check,
    endpoint: '/api/mock/approved-offer',
    description: '发送审批额度、状态和退回/拒绝原因。',
    fields: [
      { prop: 'amount', label: '审批金额', type: 'number', min: 1, step: 1000 },
      { prop: 'status', label: '状态', type: 'select', options: enumOptions.value?.approved_offer_statuses ?? [] },
      {
        prop: 'failure_reason_index',
        label: '退回原因',
        type: 'select',
        options: reasonOptions.value.map((item) => ({ label: item.label, value: item.index })),
        visible: (form) => form.status === 'RETURNED',
      },
      {
        prop: 'rejection_reason',
        label: '拒绝原因',
        type: 'select',
        options: approvedRejectionOptions.value.map((item) => ({ label: item.label, value: item.value })),
        visible: (form) => form.status === 'REJECTED',
      },
    ],
  },
  {
    key: 'pspStart',
    title: 'PSP 开始',
    icon: Promotion,
    endpoint: '/api/mock/psp-start',
    description: '发送 PSP started 状态。',
    fields: [{ prop: 'status', label: '状态', type: 'select', options: enumOptions.value?.psp_start_statuses ?? [] }],
  },
  {
    key: 'pspCompleted',
    title: 'PSP 完成',
    icon: Check,
    endpoint: '/api/mock/psp-completed',
    description: '发送 PSP completed 状态。',
    fields: [{ prop: 'status', label: '状态', type: 'select', options: enumOptions.value?.psp_completed_statuses ?? [] }],
  },
  {
    key: 'esign',
    title: '电子签',
    icon: Document,
    endpoint: '/api/mock/esign',
    description: '发送签约金额和签约结果。',
    fields: [
      { prop: 'signed_amount', label: '签约金额', type: 'number', min: 1, step: 1000 },
      { prop: 'status', label: '状态', type: 'select', options: enumOptions.value?.esign_statuses ?? [] },
    ],
  },
  {
    key: 'drawdown',
    title: '放款',
    icon: Promotion,
    endpoint: '/api/mock/drawdown',
    description: '提交放款金额、状态和失败原因。',
    fields: [
      { prop: 'amount', label: '放款金额', type: 'number', min: 0.01, step: 1000 },
      { prop: 'status', label: '状态', type: 'select', options: enumOptions.value?.drawdown_statuses ?? [] },
      {
        prop: 'failure_reason_index',
        label: '失败原因',
        type: 'select',
        options: drawdownReasonOptions.value.map((item) => ({ label: `${item.code} ${item.label}`, value: item.index })),
        visible: (form) => form.status === 'REJECTED',
      },
    ],
  },
  {
    key: 'repaymentStart',
    title: '还款开始',
    icon: Refresh,
    endpoint: '/api/mock/repayment-start',
    description: '发送还款开始通知。',
    fields: [
      { prop: 'principal_amount', label: '本金', type: 'number', min: 0.01, step: 100 },
      { prop: 'outstanding_amount', label: '剩余金额', type: 'number', min: 0, step: 100 },
    ],
  },
  {
    key: 'repayment',
    title: '还款结果',
    icon: Refresh,
    endpoint: '/api/mock/repayment',
    description: '发送还款结果和失败原因。',
    fields: [
      { prop: 'principal_amount', label: '本金', type: 'number', min: 0.01, step: 100 },
      { prop: 'outstanding_amount', label: '剩余金额', type: 'number', min: 0, step: 100 },
      { prop: 'status', label: '状态', type: 'select', options: enumOptions.value?.repayment_statuses ?? [] },
      {
        prop: 'failure_reason_index',
        label: '失败原因',
        type: 'select',
        options: repaymentReasonOptions.value.map((item) => ({ label: `${item.code} ${item.label}`, value: item.index })),
        visible: (form) => form.status === 'Failure',
      },
    ],
  },
  {
    key: 'systemEvent',
    title: '系统事件通知',
    icon: Monitor,
    endpoint: '/api/mock/system-event',
    description: '发送 system events 通知。',
    fields: [
      { prop: 'event_type', label: '事件类型', type: 'select', options: enumOptions.value?.system_event_types ?? [] },
      { prop: 'application_unique_id', label: 'Application Unique ID', type: 'text', placeholder: '可空，使用当前会话值' },
      {
        prop: 'error_code',
        label: '错误码',
        type: 'select',
        options: ['B-6003', 'B-6005'],
        visible: (form) => form.event_type === 'EXCEPTION-APPLICATION-CREATION',
      },
    ],
  },
  {
    key: 'applicationAbandon',
    title: 'Abandon',
    icon: Monitor,
    endpoint: '/api/mock/application-abandon',
    description: '发送 application.status Abandoned 通知。',
    fields: [
      {
        prop: 'abandon_reason',
        label: 'Abandon Reason',
        type: 'select',
        options: applicationAbandonOptions.value.map((item) => ({ label: item.label, value: item.value })),
      },
    ],
  },
  {
    key: 'pspHsbcStart',
    title: 'PSP 开始 HSBC',
    icon: Promotion,
    endpoint: '/api/mock/psp-hsbc-start',
    description: '发送 HSBC 特殊 PSP started 通知。',
    fields: [],
  },
  {
    key: 'pspHsbcCompleted',
    title: 'PSP 完成 HSBC',
    icon: Check,
    endpoint: '/api/mock/psp-hsbc-completed',
    description: '发送 HSBC 特殊 PSP completed 通知。',
    fields: [{ prop: 'result', label: '结果', type: 'select', options: ['SUCCESS', 'FAIL'] }],
  },
])

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
  const savedDrawerWidth = Number(window.localStorage.getItem('mockapi-drawer-width'))
  if (savedTheme) {
    darkMode.value = savedTheme === 'dark'
  } else {
    darkMode.value = window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
  }
  if (Number.isFinite(savedDrawerWidth) && savedDrawerWidth >= 320 && savedDrawerWidth <= 880) {
    aiDrawerWidth.value = savedDrawerWidth
  }
  await Promise.all([refreshHealth(), loadEnums(), loadSessions()])
  activePanels.value = operations.value.slice(0, 4).map((item) => item.key)
})

onBeforeUnmount(() => {
  closeSocket()
  stopAiResize()
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
    pushActivity('error', '注册失败', normalizeError(error))
  } finally {
    registering.value = false
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

function openLogSystem() {
  currentView.value = 'logs'
  runLogSearch()
}

function backToConsole() {
  currentView.value = 'console'
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

function openAiDrawer() {
  aiExecutionEnv.value = sessionSummary.value?.env || connectionForm.env || registerForm.env || 'sit'
  aiDrawerOpen.value = true
}

function closeAiDrawer() {
  aiDrawerOpen.value = false
}

function startAiResize(event) {
  aiResizing.value = true
  document.body.classList.add('ai-resizing')
  window.addEventListener('mousemove', onAiResize)
  window.addEventListener('mouseup', stopAiResize)
  event.preventDefault()
}

function onAiResize(event) {
  if (!aiResizing.value) return
  const nextWidth = Math.min(Math.max(window.innerWidth - event.clientX, 320), 880)
  aiDrawerWidth.value = nextWidth
}

function stopAiResize() {
  if (!aiResizing.value) return
  aiResizing.value = false
  document.body.classList.remove('ai-resizing')
  window.removeEventListener('mousemove', onAiResize)
  window.removeEventListener('mouseup', stopAiResize)
  window.localStorage.setItem('mockapi-drawer-width', String(aiDrawerWidth.value))
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
    preferred_currency: sessionSummary.value?.preferred_currency,
    selected_journey: registerForm.journey,
    recent_logs: eventLogs.value.slice(0, 20),
    recent_activities: activityFeed.value.slice(0, 12),
  }
}
</script>

<template>
  <div class="app-shell" :class="{ 'theme-dark': darkMode }">
    <section class="hero-panel">
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
        <button class="hero-action" type="button" @click="openLogSystem">
          <el-icon><Monitor /></el-icon>
          <span>日志系统</span>
        </button>
        <button class="hero-action" type="button" @click="openAiDrawer">
          <el-icon><ChatLineRound /></el-icon>
          <span>AI 助手</span>
        </button>
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
                <div class="form-row">
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
                </div>
                <el-form-item>
                  <el-switch v-model="registerForm.offline" active-text="线下模式" inactive-text="线上模式" />
                </el-form-item>
                <el-button type="success" :icon="Promotion" :loading="registering" @click="handleRegister">
                  执行注册
                </el-button>
              </el-form>
            </div>
          </div>

          <div v-if="registerResult" class="result-strip">
            <span class="result-title">最近一次注册结果</span>
            <p class="result-hint">{{ registerStatusMessage }}</p>
            <pre>{{ JSON.stringify(registerResult, null, 2) }}</pre>
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

          <el-collapse v-model="activePanels" class="operation-panels">
            <el-collapse-item v-for="operation in operations" :key="operation.key" :name="operation.key">
              <template #title>
                <div class="collapse-title">
                  <el-icon><component :is="operation.icon" /></el-icon>
                  <span>{{ operation.title }}</span>
                </div>
              </template>

              <div class="operation-body">
                <p class="operation-description">{{ operation.description }}</p>
                <code class="endpoint-chip">{{ operation.endpoint }}</code>
                <el-form label-position="top" class="tight-form">
                  <div class="operation-fields" :class="{ empty: operation.fields.length === 0 }">
                    <template v-if="operation.fields.length">
                      <template v-for="field in operation.fields" :key="`${operation.key}-${field.prop}`">
                        <el-form-item v-if="!field.visible || field.visible(operationForms[operation.key])" :label="field.label">
                          <el-input
                            v-if="field.type === 'text'"
                            v-model="operationForms[operation.key][field.prop]"
                            :placeholder="field.placeholder"
                          />
                          <el-input-number
                            v-else-if="field.type === 'number'"
                            v-model="operationForms[operation.key][field.prop]"
                            :min="field.min"
                            :step="field.step || 1"
                            controls-position="right"
                            class="full-width"
                          />
                          <el-select v-else-if="field.type === 'select'" v-model="operationForms[operation.key][field.prop]">
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
                    :loading="runningOperationKey === operation.key"
                    @click="handleOperationRun(operation)"
                  >
                    执行 {{ operation.title }}
                  </el-button>
                </el-form>

                <div v-if="operationResults[operation.key]" class="result-strip">
                  <span class="result-title">最近一次执行结果</span>
                  <pre>{{ JSON.stringify(operationResults[operation.key], null, 2) }}</pre>
                </div>
              </div>
            </el-collapse-item>
          </el-collapse>
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
                <h2>实时日志</h2>
                <p>{{ logStatusText }}</p>
              </div>
              <el-button size="small" plain :disabled="eventLogs.length === 0" @click="clearLogs">清空</el-button>
            </div>
          </template>

          <div class="log-panel">
            <div v-if="eventLogs.length === 0" class="log-empty">连接 session 后显示 WebSocket 实时日志。</div>
            <div v-for="entry in eventLogs" :key="`${entry.timestamp}-${entry.formatted}`" class="log-entry">
              <div class="log-entry-head">
                <el-tag size="small" :type="levelTagType(entry.level)">{{ entry.level || 'INFO' }}</el-tag>
                <span>{{ entry.timestamp }}</span>
              </div>
              <pre>{{ entry.formatted || entry.message || JSON.stringify(entry, null, 2) }}</pre>
            </div>
          </div>
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

    <el-drawer
      v-model="aiDrawerOpen"
      direction="rtl"
      :size="`${aiDrawerWidth}px`"
      class="ai-drawer"
      :with-header="false"
    >
      <div class="ai-drawer-shell">
        <button
          class="ai-resize-handle"
          type="button"
          aria-label="resize ai drawer"
          @mousedown="startAiResize"
        />
        <div class="ai-drawer-head">
          <div>
            <h2>AI 助手</h2>
            <p>DPU mock / SQL 辅助助手。</p>
          </div>
          <div class="ai-drawer-actions">
            <el-button :icon="Delete" text @click="clearAiChat">清空</el-button>
            <el-button :icon="Delete" text @click="closeAiDrawer">关闭</el-button>
          </div>
        </div>

        <div class="ai-chat">
          <div class="ai-exec-row">
            <span>执行环境</span>
            <el-select v-model="aiExecutionEnv" size="small" class="ai-exec-select">
              <el-option
                v-for="env in enumOptions?.environments ?? defaultEnvironments"
                :key="`ai-${env}`"
                :label="env"
                :value="env"
              />
            </el-select>
          </div>

          <div class="ai-chat-head">
            <span>对话</span>
            <el-tag size="small" :type="aiSending ? 'warning' : 'success'">{{ aiSending ? '处理中' : '就绪' }}</el-tag>
          </div>

          <div class="ai-chat-body">
            <div v-if="aiMessages.length === 0" class="chat-empty">
              你可以问我 DPU mock相关问题或执行SQL，也可以直接让我创建账号或执行接口。
            </div>
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

          <div class="ai-chat-input">
            <el-input
              v-model="aiInput"
              type="textarea"
              :rows="4"
              placeholder="例如：在 uat 环境为我创建一个线下 FP-USD 账号 / 执行这条 SQL / 帮我看当前会话状态"
              @keydown.enter.exact.prevent="handleAiSend"
            />
            <div class="ai-chat-actions">
              <el-button :icon="ChatDotRound" @click="clearAiChat">重置</el-button>
              <el-button type="primary" :icon="Position" :loading="aiSending" @click="handleAiSend">发送</el-button>
            </div>
          </div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>
