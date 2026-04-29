<template>
  <div class="hsbc-page">
    <!-- 顶部导航栏 -->
    <header class="hsbc-header">
      <div class="hsbc-logo">
        <svg width="40" height="28" viewBox="0 0 40 28" fill="none">
          <rect x="0.5" y="0.5" width="39" height="27" rx="3" stroke="#ccc" fill="white"/>
          <polygon points="8,6 20,14 8,22" fill="#DB0011"/>
          <polygon points="32,6 20,14 32,22" fill="#DB0011"/>
          <polygon points="8,6 32,6 20,14" fill="white"/>
          <polygon points="8,22 32,22 20,14" fill="white"/>
          <polygon points="8,6 20,6 20,14" fill="#DB0011"/>
          <polygon points="32,22 20,22 20,14" fill="#DB0011"/>
        </svg>
        <span class="logo-text">HSBC Express Finance</span>
        <svg width="8" height="14" viewBox="0 0 8 14" fill="none" class="logo-chevron">
          <path d="M1 1L7 7L1 13" stroke="#333" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
    </header>

    <!-- 主体内容 -->
    <div class="hsbc-main">
      <!-- 左侧表单区 -->
      <div class="hsbc-form-area">
        <p class="form-subtitle">{{ t('login.subtitle') }}</p>
        <h1 class="form-title" v-if="!isLoginMode">{{ t('login.create_title') }}</h1>
        <h1 class="form-title" v-else>{{ t('login.login_title') }}</h1>

        <!-- 手机号 -->
        <div class="field-group">
          <label class="field-label">{{ t('login.mobile') }}</label>
          <div class="phone-row">
            <div class="country-code">
              <span>+86</span>
              <svg width="10" height="6" viewBox="0 0 10 6" fill="none">
                <path d="M1 1L5 5L9 1" stroke="#333" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </div>
            <input
              class="phone-input"
              :class="{ error: errors.phone }"
              v-model="form.phone"
              type="tel"
              maxlength="11"
              :placeholder="t('login.mobile')"
              @blur="validateField('phone')"
            />
          </div>
          <div v-if="errors.phone" class="error-text">{{ errors.phone }}</div>
        </div>

        <!-- 验证码 -->
        <div class="field-group" v-if="!passwordMode">
          <label class="field-label">{{ t('login.verify_code') }}</label>
          <div class="code-row">
            <div class="code-boxes">
              <input
                v-for="(_, idx) in 6"
                :key="idx"
                :ref="el => { if (el) codeRefs[idx] = el }"
                class="code-box"
                :class="{ filled: codeDigits[idx] }"
                type="text"
                inputmode="numeric"
                maxlength="1"
                v-model="codeDigits[idx]"
                @input="handleCodeInput(idx)"
                @keydown.backspace="handleCodeBackspace(idx)"
                @paste="handlePaste($event, idx)"
              />
            </div>
            <button
              class="get-code-btn"
              :disabled="countdown > 0 || !form.phone"
              @click="handleSendCode"
            >
              {{ countdown > 0 ? `${countdown}s` : t('login.get_code') }}
            </button>
          </div>
        </div>

        <!-- 密码 -->
        <template v-if="isLoginMode">
          <div class="field-group">
            <label class="field-label">{{ t('login.password') }}</label>
            <div class="password-wrap">
              <input
                class="phone-input full-radius"
                :type="showPwd ? 'text' : 'password'"
                v-model="form.password"
                :placeholder="t('login.password')"
              />
              <span class="pwd-toggle" @click="showPwd = !showPwd">{{ showPwd ? t('login.hide') : t('login.show') }}</span>
            </div>
          </div>

          <div class="forgot-row">
            <a class="forgot-link">{{ t('login.forgot_pwd') }}</a>
          </div>
        </template>

        <!-- 自动登录勾选 -->
        <div class="auto-login" v-if="isLoginMode">
          <label class="checkbox-label">
            <input type="checkbox" v-model="autoLogin" />
            <span>{{ t('login.remember') }}</span>
          </label>
        </div>

        <!-- 已有账号链接 -->
        <div class="account-link">
          <template v-if="!isLoginMode">
            {{ t('login.have_account') }}
            <a @click="isLoginMode = true">{{ t('login.log_in') }} <span class="chevron">&rsaquo;</span></a>
          </template>
          <template v-else>
            {{ t('login.no_account') }}
            <a @click="isLoginMode = false">{{ t('login.register') }} <span class="chevron">&rsaquo;</span></a>
          </template>
        </div>

        <!-- 底部操作 -->
        <div class="action-row">
          <a class="back-link" @click="$router.back()">
            <span class="chevron-back">&lsaquo;</span> {{ t('common.back') }}
          </a>
          <button class="btn-next" :disabled="loading" @click="handleSubmit">
            <span v-if="loading" class="loading-spinner"></span>
            <span v-else>{{ t('common.next') }}</span>
          </button>
        </div>
      </div>

      <!-- 右侧香港夜景图片 -->
      <div class="hsbc-image-area">
        <img
          src="https://images.unsplash.com/photo-1536599018102-9f803c140fc1?w=1200&h=800&fit=crop"
          alt="Hong Kong skyline at night"
          class="cover-image"
        />
        <div class="chat-fab">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
            <path d="M21 11.5a8.38 8.38 0 01-.9 3.8 8.5 8.5 0 01-7.6 4.7 8.38 8.38 0 01-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 01-.9-3.8 8.5 8.5 0 014.7-7.6 8.38 8.38 0 013.8-.9h.5a8.48 8.48 0 018 8v.5z" stroke="white" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <span>{{ t('login.chat') }}</span>
        </div>
      </div>
    </div>

    <!-- 底部页脚 -->
    <footer class="hsbc-footer">
      <div class="footer-links">
        <a>{{ t('footer.about') }}</a>
        <a>{{ t('footer.terms') }}</a>
        <a>{{ t('footer.privacy') }}</a>
        <a>{{ t('footer.hyperlink') }}</a>
        <span class="lang-switch" @click="langSwitcherRef?.open()">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <circle cx="7" cy="7" r="5.5" stroke="#333" stroke-width="1"/>
            <ellipse cx="7" cy="7" rx="3" ry="5.5" stroke="#333" stroke-width="0.8"/>
            <line x1="1.5" y1="5" x2="12.5" y2="5" stroke="#333" stroke-width="0.7"/>
            <line x1="1.5" y1="9" x2="12.5" y2="9" stroke="#333" stroke-width="0.7"/>
          </svg>
          {{ t('footer.lang_label') }}
        </span>
      </div>
      <p class="footer-desc">{{ t('footer.desc') }}</p>
      <p class="footer-copyright">{{ t('footer.copyright') }}</p>
    </footer>

    <LangSwitcher ref="langSwitcherRef" />
    <div v-if="toast" :class="['toast', toast.type]">{{ toast.msg }}</div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import { sendSmsCode, loginBySms, loginByPassword, register } from '../api/index.js'
import { validatePhone, validatePassword } from '../utils/validators.js'
import { useI18n } from '../utils/i18n.js'
import LangSwitcher from '../components/LangSwitcher.vue'

const router = useRouter()
const authStore = useAuthStore()
const { t } = useI18n()

const langSwitcherRef = ref(null)
const isLoginMode = ref(false)
const passwordMode = computed(() => isLoginMode.value && form.password && !fullCode.value)
const loading = ref(false)
const showPwd = ref(false)
const autoLogin = ref(false)
const countdown = ref(0)
const toast = ref(null)
const codeRefs = ref([])
const codeDigits = reactive(['', '', '', '', '', ''])

const form = reactive({ phone: '', password: '' })
const errors = reactive({ phone: '' })

const fullCode = computed(() => codeDigits.join(''))

function validateField(field) {
  if (field === 'phone') errors.phone = validatePhone(form.phone)
}

function showToast(msg, type = 'error') {
  toast.value = { msg, type }
  setTimeout(() => { toast.value = null }, 3000)
}

function handleCodeInput(idx) {
  codeDigits[idx] = codeDigits[idx].replace(/\D/g, '')
  if (codeDigits[idx] && idx < 5) {
    codeRefs.value[idx + 1]?.focus()
  }
}

function handleCodeBackspace(idx) {
  if (!codeDigits[idx] && idx > 0) {
    codeRefs.value[idx - 1]?.focus()
  }
}

function handlePaste(e, idx) {
  if (idx !== 0) return
  e.preventDefault()
  const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6)
  for (let i = 0; i < 6; i++) {
    codeDigits[i] = pasted[i] || ''
  }
  const focusIdx = Math.min(pasted.length, 5)
  codeRefs.value[focusIdx]?.focus()
}

async function handleSendCode() {
  errors.phone = validatePhone(form.phone)
  if (errors.phone) return

  try {
    const res = await sendSmsCode(form.phone)
    if (res.code === 0) {
      countdown.value = 60
      const timer = setInterval(() => {
        countdown.value--
        if (countdown.value <= 0) clearInterval(timer)
      }, 1000)
      showToast(t('login.code_sent'), 'success')
    } else {
      showToast(res.message)
    }
  } catch {
    showToast(t('common.network_error'))
  }
}

async function handleSubmit() {
  errors.phone = validatePhone(form.phone)
  if (errors.phone) return

  if (isLoginMode.value && form.password) {
    loading.value = true
    try {
      const res = await loginByPassword(form.phone, form.password)
      if (res.code === 0) {
        authStore.setLogin(res.data.access_token, form.phone)
        showToast(t('login.login_success'), 'success')
        setTimeout(() => router.push('/dashboard'), 500)
      } else {
        showToast(res.message)
      }
    } catch {
      showToast(t('common.network_error'))
    } finally {
      loading.value = false
    }
    return
  }

  if (fullCode.value.length !== 6) {
    showToast(t('login.enter_code'))
    return
  }

  loading.value = true
  try {
    let res
    if (isLoginMode.value) {
      res = await loginBySms(form.phone, fullCode.value)
    } else {
      const regRes = await register({
        phone: form.phone,
        code: fullCode.value,
        password: 'Aa11111111',
        confirm_password: 'Aa11111111',
      })
      if (regRes.code === 0 || regRes.code === 409) {
        const smsRes = await sendSmsCode(form.phone)
        if (smsRes.code === 0) {
          res = await loginBySms(form.phone, smsRes.data.code)
        } else {
          showToast(smsRes.message)
          loading.value = false
          return
        }
      } else {
        showToast(regRes.message)
        loading.value = false
        return
      }
    }

    if (res && res.code === 0) {
      authStore.setLogin(res.data.access_token, form.phone)
      showToast(t('login.login_success'), 'success')
      setTimeout(() => router.push('/dashboard'), 500)
    } else if (res) {
      showToast(res.message)
    }
  } catch {
    showToast(t('common.network_error'))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.hsbc-page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: #fff;
}

.hsbc-header {
  display: flex;
  align-items: center;
  height: 56px;
  padding: 0 32px;
  border-bottom: 1px solid #eee;
  background: #fff;
  flex-shrink: 0;
}
.hsbc-logo {
  display: flex;
  align-items: center;
  gap: 10px;
}
.logo-text {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  letter-spacing: 0.3px;
}
.logo-chevron {
  margin-left: 2px;
  opacity: 0.5;
}

.hsbc-main {
  display: flex;
  flex: 1;
  min-height: 0;
}

.hsbc-form-area {
  flex: 0 0 50%;
  max-width: 620px;
  padding: 48px 56px 40px;
  display: flex;
  flex-direction: column;
}
.form-subtitle {
  font-size: 14px;
  color: #666;
  margin-bottom: 8px;
  font-weight: 400;
}
.form-title {
  font-size: 36px;
  font-weight: 300;
  color: #333;
  line-height: 1.25;
  margin-bottom: 40px;
  letter-spacing: -0.3px;
}

.field-group { margin-bottom: 24px; }
.field-label {
  display: block;
  font-size: 14px;
  color: #333;
  margin-bottom: 8px;
  font-weight: 400;
}

.phone-row { display: flex; }
.country-code {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 14px;
  height: 44px;
  border: 1px solid #ccc;
  border-right: none;
  border-radius: 4px 0 0 4px;
  background: #fff;
  font-size: 14px;
  color: #333;
  cursor: pointer;
}
.phone-input {
  flex: 1;
  height: 44px;
  border: 1px solid #ccc;
  border-radius: 0 4px 4px 0;
  padding: 0 12px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
  background: #fff;
}
.phone-input.full-radius { border-radius: 4px; width: 100%; }
.phone-input:focus { border-color: #333; }
.phone-input.error { border-color: #DB0011; }

.password-wrap { position: relative; }
.pwd-toggle {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 13px;
  color: #666;
  cursor: pointer;
  user-select: none;
}
.pwd-toggle:hover { color: #DB0011; }

.forgot-row {
  margin-bottom: 16px;
  text-align: right;
}
.forgot-link {
  font-size: 13px;
  color: #333;
  cursor: pointer;
  text-decoration: underline;
}
.forgot-link:hover { color: #DB0011; }

.auto-login {
  margin-bottom: 20px;
}
.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #666;
  cursor: pointer;
}
.checkbox-label input[type="checkbox"] {
  width: 16px;
  height: 16px;
  accent-color: #DB0011;
}

.code-row {
  display: flex;
  align-items: center;
  gap: 16px;
}
.code-boxes { display: flex; gap: 8px; }
.code-box {
  width: 44px;
  height: 44px;
  border: 1px solid #ccc;
  border-radius: 4px;
  text-align: center;
  font-size: 20px;
  font-weight: 500;
  outline: none;
  transition: border-color 0.2s;
  background: #fff;
  color: #333;
}
.code-box:focus { border-color: #333; }
.code-box.filled { border-color: #333; }
.get-code-btn {
  height: 44px;
  padding: 0 16px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: #fff;
  font-size: 14px;
  color: #333;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s;
}
.get-code-btn:hover:not(:disabled) {
  border-color: #333;
  color: #DB0011;
}
.get-code-btn:disabled {
  color: #bbb;
  border-color: #e0e0e0;
  cursor: not-allowed;
}

.account-link {
  font-size: 14px;
  color: #333;
  margin-bottom: 32px;
  line-height: 1.6;
}
.account-link a {
  color: #333;
  cursor: pointer;
  text-decoration: underline;
}
.account-link a:hover { color: #DB0011; }
.chevron { font-size: 16px; font-weight: 300; }

.action-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: auto;
  padding-top: 24px;
}
.back-link {
  font-size: 14px;
  color: #333;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  text-decoration: none;
  transition: color 0.2s;
}
.back-link:hover { color: #DB0011; }
.chevron-back { font-size: 20px; line-height: 1; }
.btn-next {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 88px;
  height: 40px;
  padding: 0 28px;
  background: #DB0011;
  color: #fff;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
}
.btn-next:hover { background: #af000e; }
.btn-next:disabled { background: #e8a0a0; cursor: not-allowed; }

.hsbc-image-area {
  flex: 1;
  min-width: 0;
  position: relative;
  display: none;
}
@media (min-width: 900px) {
  .hsbc-image-area { display: block; }
}
.cover-image {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.chat-fab {
  position: absolute;
  bottom: 24px;
  right: 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  background: #00847F;
  border-radius: 12px;
  padding: 12px 16px;
  cursor: pointer;
  box-shadow: 0 4px 16px rgba(0,0,0,0.2);
  transition: box-shadow 0.2s;
}
.chat-fab:hover { box-shadow: 0 6px 24px rgba(0,0,0,0.3); }
.chat-fab span {
  color: #fff;
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
}

.hsbc-footer {
  border-top: 1px solid #eee;
  padding: 20px 32px;
  background: #fff;
  flex-shrink: 0;
}
.footer-links {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  margin-bottom: 12px;
  align-items: center;
}
.footer-links a {
  font-size: 12px;
  color: #333;
  cursor: pointer;
  text-decoration: none;
}
.footer-links a:hover { text-decoration: underline; }
.lang-switch {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #333;
  cursor: pointer;
}
.footer-desc {
  font-size: 11px;
  color: #888;
  line-height: 1.6;
  margin-bottom: 8px;
}
.footer-copyright {
  font-size: 11px;
  color: #888;
  text-align: right;
}

.error-text { color: #DB0011; font-size: 12px; margin-top: 4px; }

@media (max-width: 899px) {
  .hsbc-form-area {
    flex: 1;
    max-width: 100%;
    padding: 32px 20px;
  }
  .form-title { font-size: 28px; }
  .hsbc-header { padding: 0 20px; }
  .hsbc-footer { padding: 16px 20px; }
}
</style>
