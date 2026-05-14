<template>
  <div class="app-shell">
    <header class="topbar">
      <button class="brand" type="button" @click="activeView = 'treehole'">
        <span class="brand-mark"></span>
        <span>心情树洞</span>
      </button>
      <nav class="view-tabs" aria-label="视图切换">
        <button :class="{ active: activeView === 'treehole' }" type="button" @click="activeView = 'treehole'">
          树洞
        </button>
        <button :class="{ active: activeView === 'admin' }" type="button" @click="activeView = 'admin'">
          管理台
        </button>
      </nav>
    </header>

    <main v-if="activeView === 'treehole'" class="workspace">
      <section class="compose-zone conversation-zone">
        <div class="section-heading">
          <p>匿名编号 {{ visitorId.slice(0, 8) }}</p>
          <h1>{{ conversationStatus === 'closed' ? '这轮倾诉已收好' : '慢慢说，我在听' }}</h1>
        </div>

        <div class="conversation-status">
          <span>{{ conversationId ? `会话 ${conversationId.slice(0, 8)}` : '新的倾诉会话' }}</span>
          <button
            v-if="conversationId && conversationStatus === 'closed'"
            class="secondary-button"
            type="button"
            @click="startNewConversation"
          >
            开启新一轮
          </button>
          <button
            v-else-if="conversationId"
            class="ghost-button"
            type="button"
            :disabled="closingConversation"
            @click="finishConversation"
          >
            结束倾诉
          </button>
        </div>

        <section class="conversation-thread" aria-label="倾诉时间线">
          <p v-if="!conversationMessages.length" class="empty-text">
            不用整理语言，先把此刻放下来。你可以一直写，直到想告别为止。
          </p>
          <article v-for="message in conversationMessages" :key="message.id" class="thread-item">
            <div class="bubble user-bubble">
              <div class="bubble-meta">
                <strong>{{ message.mood }}</strong>
                <small>{{ formatTime(message.created_at) }}</small>
              </div>
              <p>{{ message.content }}</p>
            </div>
            <div class="bubble treehole-bubble">
              <div class="bubble-meta">
                <strong>树洞回应</strong>
                <span class="tag">{{ sourceLabel(message.analysis_source) }}</span>
              </div>
              <p>{{ message.ai_reply }}</p>
            </div>
            <div v-if="message.manual_reply" class="bubble admin-bubble">
              <div class="bubble-meta">
                <strong>管理员留言</strong>
                <small>{{ formatTime(message.updated_at) }}</small>
              </div>
              <p>{{ message.manual_reply }}</p>
            </div>
          </article>
        </section>

        <form class="compose-form" @submit.prevent="submitEntry">
          <label class="field">
            <span>此刻心情</span>
            <select v-model="entryForm.mood" :disabled="conversationStatus === 'closed'">
              <option v-for="mood in moods" :key="mood" :value="mood">{{ mood }}</option>
            </select>
          </label>
          <label class="field">
            <span>想说的话</span>
            <textarea
              v-model="entryForm.content"
              maxlength="2000"
              :disabled="conversationStatus === 'closed'"
              placeholder="你可以继续说，也可以说“再见”“今天先到这”来结束这轮倾诉。"
            ></textarea>
          </label>
          <div class="form-footer">
            <span>{{ entryForm.content.length }}/2000</span>
            <button class="primary-button" type="submit" :disabled="submitting || conversationStatus === 'closed'">
              {{ submitting ? '正在回应' : '继续倾诉' }}
            </button>
          </div>
          <p v-if="entryError" class="error-text">{{ entryError }}</p>
        </form>
      </section>

      <aside class="side-rail">
        <section class="identity-panel">
          <div class="panel-header">
            <h2>{{ userToken ? '已登录' : '可选登录' }}</h2>
            <button v-if="userToken" class="ghost-button" type="button" @click="logoutUser">退出</button>
          </div>
          <div v-if="userToken" class="signed-in">
            <strong>{{ user?.display_name || user?.username }}</strong>
            <span>当前会话会继续保留，不会因为登录被拆开。</span>
          </div>
          <form v-else class="auth-form" @submit.prevent="submitUserAuth">
            <div class="segmented">
              <button :class="{ active: authMode === 'login' }" type="button" @click="authMode = 'login'">
                登录
              </button>
              <button :class="{ active: authMode === 'register' }" type="button" @click="authMode = 'register'">
                注册
              </button>
            </div>
            <input v-model="userForm.username" autocomplete="username" placeholder="用户名" />
            <input v-model="userForm.password" autocomplete="current-password" type="password" placeholder="密码" />
            <input
              v-if="authMode === 'register'"
              v-model="userForm.display_name"
              autocomplete="nickname"
              placeholder="显示名"
            />
            <button class="secondary-button" type="submit">{{ authMode === 'login' ? '登录' : '注册并登录' }}</button>
            <p v-if="authError" class="error-text">{{ authError }}</p>
          </form>
        </section>

        <section class="history-panel">
          <div class="panel-header">
            <h2>我的树洞</h2>
            <button class="ghost-button" type="button" @click="refreshMine">刷新</button>
          </div>
          <div v-if="myEntries.length" class="entry-list compact">
            <article v-for="entry in myEntries" :key="entry.id" class="entry-row">
              <div>
                <span :class="['risk-dot', entry.risk_level]"></span>
                <strong>{{ entry.mood }}</strong>
                <small>{{ formatTime(entry.created_at) }}</small>
              </div>
              <p>{{ entry.summary }}</p>
            </article>
          </div>
          <p v-else class="empty-text">这里会保留你自己的记录。</p>
        </section>
      </aside>

      <section class="recent-strip">
        <div class="panel-header">
          <h2>最近回声</h2>
          <button class="ghost-button" type="button" @click="refreshRecent">刷新</button>
        </div>
        <div v-if="recentEntries.length" class="recent-grid">
          <article v-for="entry in recentEntries" :key="entry.id" class="recent-item">
            <span>{{ entry.emotion_label }}</span>
            <p>{{ entry.summary }}</p>
            <small>{{ formatTime(entry.created_at) }}</small>
          </article>
        </div>
        <p v-else class="empty-text">还没有公开的低风险回声。</p>
      </section>
    </main>

    <main v-else class="admin-workspace">
      <section v-if="!adminToken" class="admin-login">
        <div class="section-heading">
          <p>Admin</p>
          <h1>树洞管理台</h1>
        </div>
        <form class="auth-form wide" @submit.prevent="submitAdminLogin">
          <input v-model="adminForm.username" autocomplete="username" placeholder="管理员账号" />
          <input v-model="adminForm.password" autocomplete="current-password" type="password" placeholder="管理员密码" />
          <button class="primary-button" type="submit">登录管理台</button>
          <p v-if="adminError" class="error-text">{{ adminError }}</p>
        </form>
      </section>

      <section v-else class="admin-panel">
        <div class="admin-header">
          <div>
            <p>Records</p>
            <h1>全部树洞记录</h1>
          </div>
          <button class="ghost-button" type="button" @click="logoutAdmin">退出管理台</button>
        </div>

        <div class="admin-filters">
          <select v-model="adminFilters.status" @change="refreshAdminEntries">
            <option value="">全部状态</option>
            <option value="visible">可见</option>
            <option value="pending_review">待处理</option>
            <option value="hidden">已隐藏</option>
            <option value="deleted">已删除</option>
          </select>
          <select v-model="adminFilters.risk_level" @change="refreshAdminEntries">
            <option value="">全部风险</option>
            <option value="low">低</option>
            <option value="medium">中</option>
            <option value="high">高</option>
          </select>
          <input v-model="adminFilters.q" @keyup.enter="refreshAdminEntries" placeholder="搜索内容、摘要或标签" />
          <button class="secondary-button" type="button" @click="refreshAdminEntries">查询</button>
        </div>

        <div v-if="adminEntries.length" class="admin-list">
          <article v-for="entry in adminEntries" :key="entry.id" class="admin-row">
            <div class="admin-row-main">
              <div class="row-meta">
                <span :class="['risk-pill', entry.risk_level]">{{ riskLabel(entry.risk_level) }}</span>
                <span class="tag">{{ entry.status }}</span>
                <span class="tag">{{ entry.conversation_status === 'closed' ? '已告别' : '倾诉中' }}</span>
                <span class="tag">{{ sourceLabel(entry.analysis_source) }}</span>
                <span>{{ entry.username || entry.visitor_id?.slice(0, 8) || '匿名' }}</span>
                <span>{{ formatTime(entry.created_at) }}</span>
              </div>
              <h3>{{ entry.summary }}</h3>
              <p>{{ entry.content }}</p>
              <blockquote>{{ entry.ai_reply }}</blockquote>
            </div>
            <div class="moderation-tools">
              <select v-model="entry.draftStatus">
                <option value="visible">可见</option>
                <option value="pending_review">待处理</option>
                <option value="hidden">隐藏</option>
                <option value="deleted">删除</option>
              </select>
              <textarea v-model="entry.draftManualReply" placeholder="管理员留言，保存后会实时弹给用户"></textarea>
              <textarea v-model="entry.draftAdminNote" placeholder="内部备注"></textarea>
              <div class="tool-actions">
                <button class="secondary-button" type="button" @click="saveAdminEntry(entry)">保存</button>
                <button class="ghost-button danger" type="button" @click="markDeleted(entry)">软删除</button>
              </div>
            </div>
          </article>
        </div>
        <p v-else class="empty-text">没有匹配的树洞记录。</p>
      </section>
    </main>

    <transition name="reply">
      <div v-if="adminToast" class="admin-toast" role="status">
        <strong>管理员给你留了话</strong>
        <p>{{ adminToast }}</p>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import {
  buildConversationWebSocketUrl,
  closeConversation,
  createEntry,
  getAdminEntries,
  getConversation,
  getMyEntries,
  getRecentEntries,
  loginAdmin,
  loginUser,
  patchAdminEntry,
  registerUser,
} from './api'

const moods = ['低落', '焦虑', '疲惫', '委屈', '生气', '麻木', '还好', '期待']
const activeView = ref('treehole')
const submitting = ref(false)
const closingConversation = ref(false)
const entryError = ref('')
const authError = ref('')
const adminError = ref('')
const adminToast = ref('')
const conversationMessages = ref([])
const conversationStatus = ref(localStorage.getItem('mood-treehole.conversationStatus') || 'active')
const conversationId = ref(localStorage.getItem('mood-treehole.conversationId') || '')
const myEntries = ref([])
const recentEntries = ref([])
const adminEntries = ref([])
const authMode = ref('login')
let conversationSocket = null
let pollingTimer = null
let toastTimer = null

function ensureVisitorId() {
  const stored = localStorage.getItem('mood-treehole.visitorId')
  if (stored) return stored
  const generated = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`
  localStorage.setItem('mood-treehole.visitorId', generated)
  return generated
}

const visitorId = ref(ensureVisitorId())
const userToken = ref(localStorage.getItem('mood-treehole.userToken') || '')
const adminToken = ref(localStorage.getItem('mood-treehole.adminToken') || '')
const user = ref(JSON.parse(localStorage.getItem('mood-treehole.user') || 'null'))

const entryForm = reactive({ mood: moods[0], content: '' })
const userForm = reactive({ username: '', password: '', display_name: '' })
const adminForm = reactive({ username: 'admin', password: '' })
const adminFilters = reactive({ status: '', risk_level: '', q: '' })

function persistConversation(id, status = 'active') {
  conversationId.value = id
  conversationStatus.value = status
  if (id) localStorage.setItem('mood-treehole.conversationId', id)
  localStorage.setItem('mood-treehole.conversationStatus', status)
}

function clearConversationSocket() {
  if (conversationSocket) {
    conversationSocket.close()
    conversationSocket = null
  }
}

function connectRealtime() {
  clearConversationSocket()
  if (!conversationId.value || conversationStatus.value === 'closed') return
  conversationSocket = new WebSocket(buildConversationWebSocketUrl(conversationId.value, visitorId.value, userToken.value))
  conversationSocket.onmessage = async (event) => {
    try {
      const payload = JSON.parse(event.data)
      if (payload.type === 'admin_reply') {
        showAdminToast(payload.manual_reply)
        await refreshConversation()
      }
    } catch {
      await refreshConversation()
    }
  }
}

function showAdminToast(text) {
  adminToast.value = text
  window.clearTimeout(toastTimer)
  toastTimer = window.setTimeout(() => {
    adminToast.value = ''
  }, 8000)
}

function startPolling() {
  window.clearInterval(pollingTimer)
  pollingTimer = window.setInterval(() => {
    if (conversationId.value && conversationStatus.value !== 'closed') refreshConversation()
  }, 12000)
}

async function refreshConversation() {
  if (!conversationId.value) return
  try {
    const conversation = await getConversation(conversationId.value, visitorId.value, userToken.value)
    conversationMessages.value = conversation.messages
    persistConversation(conversation.id, conversation.status)
    if (conversation.status === 'closed') clearConversationSocket()
  } catch {
    startNewConversation()
  }
}

async function submitEntry() {
  entryError.value = ''
  submitting.value = true
  try {
    const entry = await createEntry(
      {
        conversation_id: conversationId.value || null,
        visitor_id: visitorId.value,
        mood: entryForm.mood,
        content: entryForm.content,
      },
      userToken.value,
    )
    entryForm.content = ''
    if (entry.visitor_id && entry.visitor_id !== visitorId.value) {
      visitorId.value = entry.visitor_id
      localStorage.setItem('mood-treehole.visitorId', entry.visitor_id)
    }
    persistConversation(entry.conversation_id, entry.conversation_status)
    await Promise.all([refreshConversation(), refreshMine(), refreshRecent()])
    connectRealtime()
    if (adminToken.value) await refreshAdminEntries()
  } catch (error) {
    entryError.value = error.message
  } finally {
    submitting.value = false
  }
}

async function finishConversation() {
  if (!conversationId.value) return
  closingConversation.value = true
  try {
    const conversation = await closeConversation(conversationId.value, { visitor_id: visitorId.value }, userToken.value)
    conversationMessages.value = conversation.messages
    persistConversation(conversation.id, conversation.status)
    clearConversationSocket()
  } catch (error) {
    entryError.value = error.message
  } finally {
    closingConversation.value = false
  }
}

function startNewConversation() {
  clearConversationSocket()
  conversationId.value = ''
  conversationStatus.value = 'active'
  conversationMessages.value = []
  localStorage.removeItem('mood-treehole.conversationId')
  localStorage.setItem('mood-treehole.conversationStatus', 'active')
}

async function submitUserAuth() {
  authError.value = ''
  try {
    const payload = { ...userForm }
    const data = authMode.value === 'register' ? await registerUser(payload) : await loginUser(payload)
    userToken.value = data.token
    user.value = data.user
    localStorage.setItem('mood-treehole.userToken', data.token)
    localStorage.setItem('mood-treehole.user', JSON.stringify(data.user))
    userForm.password = ''
    await refreshMine()
    connectRealtime()
  } catch (error) {
    authError.value = error.message
  }
}

function logoutUser() {
  userToken.value = ''
  user.value = null
  localStorage.removeItem('mood-treehole.userToken')
  localStorage.removeItem('mood-treehole.user')
  refreshMine()
  connectRealtime()
}

async function refreshMine() {
  try {
    myEntries.value = await getMyEntries(visitorId.value, userToken.value)
  } catch {
    myEntries.value = []
  }
}

async function refreshRecent() {
  try {
    recentEntries.value = await getRecentEntries()
  } catch {
    recentEntries.value = []
  }
}

async function submitAdminLogin() {
  adminError.value = ''
  try {
    const data = await loginAdmin(adminForm)
    adminToken.value = data.token
    localStorage.setItem('mood-treehole.adminToken', data.token)
    adminForm.password = ''
    await refreshAdminEntries()
  } catch (error) {
    adminError.value = error.message
  }
}

function logoutAdmin() {
  adminToken.value = ''
  adminEntries.value = []
  localStorage.removeItem('mood-treehole.adminToken')
}

async function refreshAdminEntries() {
  if (!adminToken.value) return
  try {
    const entries = await getAdminEntries(adminFilters, adminToken.value)
    adminEntries.value = entries.map((entry) => ({
      ...entry,
      draftStatus: entry.status,
      draftManualReply: entry.manual_reply || '',
      draftAdminNote: entry.admin_note || '',
    }))
  } catch (error) {
    adminError.value = error.message
    if (error.message.includes('登录')) logoutAdmin()
  }
}

async function saveAdminEntry(entry) {
  await patchAdminEntry(
    entry.id,
    {
      status: entry.draftStatus,
      manual_reply: entry.draftManualReply,
      admin_note: entry.draftAdminNote,
    },
    adminToken.value,
  )
  await refreshAdminEntries()
  await refreshRecent()
}

async function markDeleted(entry) {
  entry.draftStatus = 'deleted'
  await saveAdminEntry(entry)
}

function riskLabel(level) {
  return { low: '低风险', medium: '中风险', high: '高风险' }[level] || level
}

function sourceLabel(source) {
  return { qwen: '千问', fallback: '本地兜底' }[source] || source
}

function formatTime(value) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

onMounted(async () => {
  await Promise.all([refreshMine(), refreshRecent()])
  if (conversationId.value) {
    await refreshConversation()
    connectRealtime()
  }
  startPolling()
  if (adminToken.value) await refreshAdminEntries()
})

onBeforeUnmount(() => {
  clearConversationSocket()
  window.clearInterval(pollingTimer)
  window.clearTimeout(toastTimer)
})
</script>
