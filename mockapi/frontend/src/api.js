import axios from 'axios'

const client = axios.create({
  timeout: 30000,
})

const isLocalHost = typeof window !== 'undefined'
  && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')

const aiClient = axios.create({
  baseURL: '',
  timeout: 60000,
})

const aiFallbackClient = axios.create({
  baseURL: isLocalHost ? 'http://127.0.0.1:8017' : '',
  timeout: 60000,
})

function unwrap(response) {
  const payload = response.data
  if (payload?.success === false) {
    throw new Error(payload.message || 'Request failed')
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

export async function fetchSessions() {
  const response = await client.get('/api/sessions')
  return unwrap(response)
}

export async function fetchLogs(params = {}) {
  const response = await client.get('/api/logs', { params })
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

export async function runMockOperation(endpoint, payload) {
  const response = await client.post(endpoint, payload)
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
