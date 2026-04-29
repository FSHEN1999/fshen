import axios from 'axios'

const client = axios.create({
  timeout: 30000,
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
