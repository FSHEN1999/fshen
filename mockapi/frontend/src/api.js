import axios from 'axios'

const client = axios.create({
  timeout: 30000,
})

const isLocalHost = typeof window !== 'undefined'
  && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')

const aiClient = axios.create({
  baseURL: '',
  timeout: 150000,
})

const aiFallbackClient = axios.create({
  baseURL: isLocalHost ? 'http://127.0.0.1:8017' : '',
  timeout: 150000,
})

function attachErrorPayload(error) {
  const payload = error?.response?.data
  if (payload) {
    error.payload = payload?.data ?? payload
  }
  return Promise.reject(error)
}

client.interceptors.response.use((response) => response, attachErrorPayload)
aiClient.interceptors.response.use((response) => response, attachErrorPayload)
aiFallbackClient.interceptors.response.use((response) => response, attachErrorPayload)

function unwrap(response) {
  const payload = response.data
  if (payload?.success === false) {
    const error = new Error(payload.message || payload.error_message || 'Request failed')
    error.payload = payload
    error.response = response
    throw error
  }
  return payload?.data ?? payload
}

export async function fetchHealth() {
  const response = await client.get('/api/health')
  return response.data
}

export async function fetchEnums() {
  const response = await client.get('/api/enums')
  return unwrap(response)
}

export async function fetchSessions(sessionId) {
  const response = await client.get('/api/sessions', {
    params: sessionId ? { session_id: sessionId } : undefined,
  })
  return unwrap(response)
}

export async function fetchLogs(params = {}) {
  const response = await client.get('/api/logs', { params })
  return unwrap(response)
}

export async function loginUser(payload) {
  const response = await client.post('/api/auth/login', payload)
  return unwrap(response)
}

export async function registerUser(payload) {
  const response = await client.post('/api/auth/register', payload)
  return unwrap(response)
}

export async function fetchContactIssues() {
  const response = await client.get('/api/contact-issues')
  return unwrap(response)
}

export async function createContactIssue(payload) {
  const response = await client.post('/api/contact-issues', payload)
  return unwrap(response)
}

export async function replyContactIssueApi(issueId, payload) {
  const response = await client.post(`/api/contact-issues/${issueId}/reply`, payload)
  return unwrap(response)
}

export async function deleteContactIssueApi(issueId) {
  const response = await client.delete(`/api/contact-issues/${issueId}`)
  return unwrap(response)
}

export async function connectSession(payload) {
  const response = await client.post('/api/connect', payload)
  return unwrap(response)
}

export async function disconnectSession(sessionId) {
  const response = await client.post('/api/disconnect', null, {
    params: { session_id: sessionId },
  })
  return unwrap(response)
}

export async function registerAccount(payload) {
  const response = await client.post('/api/register', payload)
  return unwrap(response)
}

export async function registerAndRunMultiShop(payload) {
  const response = await client.post('/api/register-and-run-multishop', payload, {
    timeout: 180000,
  })
  return unwrap(response)
}

export async function fetchDowsureMerchantAccounts(sessionId) {
  const response = await client.get('/api/mock/dowsure-merchant-accounts', {
    params: { session_id: sessionId },
  })
  return unwrap(response)
}

export async function fetchPspAuthorizationRows(sessionId) {
  const response = await client.get('/api/mock/psp-authorization-rows', {
    params: { session_id: sessionId },
  })
  return unwrap(response)
}

export async function runMockOperation(endpoint, payload) {
  const response = await client.post(endpoint, payload)
  return unwrap(response)
}

export async function runScenarioApi(endpoint, payload, options = {}) {
  const response = await client.post(endpoint, payload, {
    timeout: options.timeout,
  })
  return unwrap(response)
}

export async function sendAiChat(payload) {
  try {
    const response = await aiClient.post('/api/ai/chat', payload)
    return unwrap(response)
  } catch (error) {
    const detail = error?.response?.data?.data?.reply || error?.response?.data?.detail || error?.message || ''
    const shouldFallback =
      String(detail).includes('QWEN_API_KEY is not configured') ||
      String(detail).includes('Network Error') ||
      String(detail).includes('ERR_ABORTED')

    if (!shouldFallback) {
      throw error
    }

    if (!isLocalHost) {
      throw error
    }

    const fallbackResponse = await aiFallbackClient.post('/api/ai/chat', payload)
    return unwrap(fallbackResponse)
  }
}
