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
  Promotion,
  Refresh,
} from '@element-plus/icons-vue'
import {
  connectSession,
  disconnectSession,
  fetchEnums,
  fetchHealth,
  fetchSessions,
  registerAccount,
  runMockOperation,
} from './api.js'

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
const liveSessions = ref([])
const eventLogs = ref([])
const activityFeed = ref([])
const registerResult = ref(null)
const registerAutoConnected = ref(false)
const wsConnected = ref(false)
const wsError = ref('')

let logSocket = null

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
  approvedOffer: { amount: 500000, status: 'APPROVED', failure_reason_index: 1 },
  pspStart: { status: 'PROCESSING' },
  pspCompleted: { status: 'SUCCESS' },
  esign: { signed_amount: 500000, status: 'SUCCESS' },
  drawdown: { amount: 100000, status: 'APPROVED', failure_reason_index: 1 },
  repaymentStart: { principal_amount: 1000, outstanding_amount: 0 },
  repayment: { principal_amount: 1000, outstanding_amount: 0, status: 'Success', failure_reason_index: 1 },
  multiShopBinding: { state: 'manual-state-demo' },
  spStatusUpdate: { platform_seller_id: '', status: 'SUCCESS', failure_reason_index: 1 },
  multiShop3plRedirect: {},
  systemEvent: {
    event_type: 'EXCEPTION-APPLICATION-CREATION',
    application_unique_id: '',
    error_code: 'B-6003',
  },
  pspHsbcStart: {},
  pspHsbcCompleted: { result: 'SUCCESS' },
})

const operationResults = reactive({})

const reasonOptions = computed(() => enumOptions.value?.returned_failure_reasons ?? [])
const drawdownReasonOptions = computed(() => enumOptions.value?.drawdown_failure_reasons ?? [])
const repaymentReasonOptions = computed(() => enumOptions.value?.repayment_failure_reasons ?? [])
const spFailureOptions = computed(() => enumOptions.value?.sp_update_failure_reasons ?? [])

const operations = computed(() => [
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
    description: '发送审批额度、状态和退回原因。',
    fields: [
      { prop: 'amount', label: '审批额度', type: 'number', min: 1, step: 1000 },
      { prop: 'status', label: '状态', type: 'select', options: enumOptions.value?.approved_offer_statuses ?? [] },
      {
        prop: 'failure_reason_index',
        label: '退回原因',
        type: 'select',
        options: reasonOptions.value.map((item) => ({ label: item.label, value: item.index })),
        visible: (form) => form.status === 'RETURNED',
      },
    ],
  },
  {
    key: 'pspStart',
    title: 'PSP 开始',
    icon: Promotion,
    endpoint: '/api/mock/psp-start',
    description: '发送 PSP started 状态。',
    fields: [
      { prop: 'status', label: '状态', type: 'select', options: enumOptions.value?.psp_start_statuses ?? [] },
    ],
  },
  {
    key: 'pspCompleted',
    title: 'PSP 完成',
    icon: Check,
    endpoint: '/api/mock/psp-completed',
    description: '发送 PSP completed 状态。',
    fields: [
      { prop: 'status', label: '状态', type: 'select', options: enumOptions.value?.psp_completed_statuses ?? [] },
    ],
  },
  {
    key: 'esign',
    title: '电子签',
    icon: Document,
    endpoint: '/api/mock/esign',
    description: '发送签约额度和结果。',
    fields: [
      { prop: 'signed_amount', label: '签约额度', type: 'number', min: 1, step: 1000 },
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
        options: drawdownReasonOptions.value.map((item) => ({
          label: `${item.code} ${item.label}`,
          value: item.index,
        })),
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
    title: '还款',
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
        options: repaymentReasonOptions.value.map((item) => ({
          label: `${item.code} ${item.label}`,
          value: item.index,
        })),
        visible: (form) => form.status === 'Failure',
      },
    ],
  },
  {
    key: 'multiShopBinding',
    title: '多店铺 SP 绑定',
    icon: Link,
    endpoint: '/api/mock/multi-shop-binding',
    description: '第一步生成多店铺绑定所需 state。',
    fields: [
      { prop: 'state', label: 'State', type: 'text', placeholder: '请输入 state' },
    ],
  },
  {
    key: 'spStatusUpdate',
    title: 'SP 状态更新',
    icon: Cpu,
    endpoint: '/api/mock/sp-status-update',
    description: '更新 SP 状态，可选择失败原因。',
    fields: [
      { prop: 'platform_seller_id', label: 'Platform Seller ID', type: 'text', placeholder: '可空，默认自动取已生成值或按 merchant_id 反查' },
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
    description: '第二步生成多店铺 3PL 跳转链接。',
    fields: [],
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
    key: 'pspHsbcStart',
    title: 'PSP 开始 HSBC',
    icon: Promotion,
    endpoint: '/api/mock/psp-hsbc-start',
    description: '发送 HSBC 版 PSP started 通知。',
    fields: [],
  },
  {
    key: 'pspHsbcCompleted',
    title: 'PSP 完成 HSBC',
    icon: Check,
    endpoint: '/api/mock/psp-hsbc-completed',
    description: '发送 HSBC 版 PSP completed 通知。',
    fields: [
      { prop: 'result', label: '结果', type: 'select', options: ['SUCCESS', 'FAIL'] },
    ],
  },
])

const sessionSummary = computed(() => {
  const current = liveSessions.value.find((item) => item.session_id === activeSessionId.value)
  if (current) return current
  return activityFeed.value.find((item) => item.kind === 'connect')?.payload ?? null
})

const logStatusText = computed(() => {
  if (!activeSessionId.value) return '未连接会话'
  if (wsConnected.value) return '实时日志已连接'
  if (wsError.value) return `日志连接异常: ${wsError.value}`
  return '日志连接中'
})

const registerStatusMessage = computed(() => {
  if (!registerResult.value) return ''
  return registerAutoConnected.value
    ? '已自动连接到新注册账号，可直接执行 mock 操作。'
    : '注册已完成，但还没有可用会话，请点击“连接 session”继续。'
})

watch(
  () => connectionForm.env,
  (value) => {
    registerForm.env = value
  },
)

onMounted(async () => {
  await Promise.all([refreshHealth(), loadEnums(), loadSessions()])
  activePanels.value = operations.value.slice(0, 4).map((item) => item.key)
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
  disconnecting.value = true
  try {
    await disconnectSession(activeSessionId.value)
    pushActivity('disconnect', '会话已断开', { session_id: activeSessionId.value })
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
        pushActivity(
          'error',
          '注册后自动连接失败',
          `${normalizeError(error)}。你也可以直接点击“连接 session”重试。`,
        )
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

function buildPayload(operation) {
  const payload = { session_id: activeSessionId.value }
  const form = operationForms[operation.key] ?? {}
  for (const field of operation.fields) {
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
  return field.options.map((option) => (
    typeof option === 'object' ? option : { label: option, value: option }
  ))
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
</script>

<template>
  <div class="app-shell">
    <section class="hero-panel">
      <div>
        <p class="eyebrow">DPU Mock Console</p>
        <h1>mock_sit Mock API 控台</h1>
        <p class="hero-copy">
          这是一个用于触发和验证 mock API 的前端控制台，支持连接会话、执行 mock 操作，并查看实时日志。
        </p>
      </div>
      <div class="hero-metrics">
        <div class="metric-card">
          <span>后端健康</span>
          <strong>{{ health }}</strong>
        </div>
        <div class="metric-card">
          <span>活动会话</span>
          <strong>{{ liveSessions.length }}</strong>
        </div>
        <div class="metric-card">
          <span>日志状态</span>
          <strong>{{ wsConnected ? 'online' : 'offline' }}</strong>
        </div>
      </div>
    </section>

    <section class="workspace-grid">
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
                      v-for="env in enumOptions?.environments ?? ['sit', 'uat', 'dev', 'preprod', 'reg', 'local']"
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
                      v-for="env in enumOptions?.environments ?? ['sit', 'uat', 'dev', 'preprod', 'reg', 'local']"
                      :key="`reg-${env}`"
                      :label="env"
                      :value="env"
                    />
                  </el-select>
                </el-form-item>
                <div class="form-row">
                  <el-form-item label="Journey">
                    <el-select v-model="registerForm.journey">
                      <el-option
                        v-for="journey in enumOptions?.journeys ?? ['200K', '500K', '2000K']"
                        :key="journey"
                        :label="journey"
                        :value="journey"
                      />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="币种">
                    <el-select v-model="registerForm.currency">
                      <el-option
                        v-for="currency in enumOptions?.currencies ?? ['USD', 'CNY']"
                        :key="currency"
                        :label="currency"
                        :value="currency"
                      />
                    </el-select>
                  </el-form-item>
                </div>
                <el-form-item>
                  <el-switch v-model="registerForm.offline" active-text="线下模式" inactive-text="标准模式" />
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
                <p>15 个操作全部接到现有 FastAPI 接口。</p>
              </div>
              <el-tag :type="activeSessionId ? 'success' : 'warning'" size="large">
                {{ activeSessionId ? `session: ${activeSessionId.slice(0, 8)}...` : '未连接 session' }}
              </el-tag>
            </div>
          </template>

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

                  <el-button type="primary" :loading="runningOperationKey === operation.key" @click="handleOperationRun(operation)">
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
              <el-button :icon="Delete" text @click="clearLogs">清空</el-button>
            </div>
          </template>

          <div class="log-panel">
            <div v-if="eventLogs.length === 0" class="log-empty">连接会话后，这里会持续显示 WebSocket 日志。</div>
            <div v-for="entry in eventLogs" :key="`${entry.timestamp}-${entry.funcName}-${entry.lineno}`" class="log-entry">
              <div class="log-entry-head">
                <el-tag size="small" :type="levelTagType(entry.level)">{{ entry.level }}</el-tag>
                <span>{{ entry.timestamp }}</span>
              </div>
              <pre>{{ entry.formatted || entry.message }}</pre>
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
  </div>
</template>
