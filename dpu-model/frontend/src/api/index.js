import axios from 'axios'
import { useAuthStore } from '../stores/auth.js'
import router from '../router/index.js'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

// 请求拦截：注入Token
api.interceptors.request.use((config) => {
  const authStore = useAuthStore()
  if (authStore.token) {
    config.headers.Authorization = `Bearer ${authStore.token}`
  }
  return config
})

// 响应拦截：统一处理错误
api.interceptors.response.use(
  (res) => res.data,
  (err) => {
    if (err.response?.status === 401) {
      const authStore = useAuthStore()
      authStore.logout()
      router.push('/login')
    }
    return Promise.reject(err)
  }
)

// ========== 认证接口 ==========
export const sendSmsCode = (phone) => api.post('/auth/sms-code', { phone })
export const loginBySms = (phone, code) => api.post('/auth/login/sms', { phone, code })
export const loginByPassword = (phone, password) => api.post('/auth/login/password', { phone, password })
export const register = (data) => api.post('/auth/register', data)

// ========== 用户信息接口 ==========
export const getProfile = () => api.get('/user/profile')
export const submitProfile = (data) => api.post('/user/profile', data)
export const submitShareholder = (data) => api.post('/user/shareholder', data)

// ========== 评估接口 ==========
export const getQuota = () => api.get('/assessment/quota')
export const applyLoan = (data) => api.post('/assessment/apply', data)

// ========== 审批接口 ==========
export const getApprovalStatus = () => api.get('/approval/status')
export const cancelApproval = () => api.post('/approval/cancel')

export default api
