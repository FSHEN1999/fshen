export const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

async function request(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(options.token ? { Authorization: `Bearer ${options.token}` } : {}),
    ...(options.headers || {}),
  }
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  })
  const text = await response.text()
  let data = null
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = { detail: text }
    }
  }
  if (!response.ok) {
    throw new Error(data?.detail || data?.message || '请求失败')
  }
  return data
}

export function createEntry(payload, token) {
  return request('/api/entries', {
    method: 'POST',
    body: JSON.stringify(payload),
    token,
  })
}

export function getConversation(conversationId, visitorId, token) {
  const query = visitorId ? `?visitor_id=${encodeURIComponent(visitorId)}` : ''
  return request(`/api/conversations/${encodeURIComponent(conversationId)}${query}`, { token })
}

export function closeConversation(conversationId, payload, token) {
  return request(`/api/conversations/${encodeURIComponent(conversationId)}/close`, {
    method: 'POST',
    body: JSON.stringify(payload),
    token,
  })
}

export function buildConversationWebSocketUrl(conversationId, visitorId, token) {
  const origin = API_BASE || window.location.origin
  const url = new URL(`/api/ws/conversations/${encodeURIComponent(conversationId)}`, origin)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  if (visitorId) url.searchParams.set('visitor_id', visitorId)
  if (token) url.searchParams.set('token', token)
  return url.toString()
}

export function getMyEntries(visitorId, token) {
  const query = token ? '' : `?visitor_id=${encodeURIComponent(visitorId)}`
  return request(`/api/me/entries${query}`, { token })
}

export function getRecentEntries() {
  return request('/api/entries/recent')
}

export function registerUser(payload) {
  return request('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function loginUser(payload) {
  return request('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function loginAdmin(payload) {
  return request('/api/admin/login', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getAdminEntries(filters, token) {
  const params = new URLSearchParams()
  if (filters.status) params.set('status', filters.status)
  if (filters.risk_level) params.set('risk_level', filters.risk_level)
  if (filters.q) params.set('q', filters.q)
  const query = params.toString() ? `?${params.toString()}` : ''
  return request(`/api/admin/entries${query}`, { token })
}

export function patchAdminEntry(id, payload, token) {
  return request(`/api/admin/entries/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
    token,
  })
}
