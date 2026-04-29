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

    <!-- 主体 -->
    <div class="hsbc-main">
      <div class="hsbc-form-area">
        <p class="form-subtitle">{{ t('login.subtitle') }}</p>
        <h1 class="form-title">{{ t('register.title') }}</h1>

        <!-- 手机号验证区 -->
        <div class="section-block">
          <div class="section-heading">{{ t('register.verify_mobile') }}</div>
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
                class="field-input"
                :class="{ error: errors.phone }"
                v-model="form.phone"
                type="tel"
                maxlength="11"
                :placeholder="t('login.mobile')"
                @blur="errors.phone = validatePhone(form.phone)"
              />
            </div>
            <div v-if="errors.phone" class="error-text">{{ errors.phone }}</div>
          </div>
          <div class="field-group">
            <label class="field-label">{{ t('login.verify_code') }}</label>
            <div class="code-row">
              <input
                class="field-input"
                v-model="form.code"
                type="text"
                maxlength="6"
                :placeholder="t('login.verify_code')"
              />
              <button
                class="get-code-btn"
                :disabled="countdown > 0 || !form.phone"
                @click="handleSendCode"
              >
                {{ countdown > 0 ? `${countdown}s` : t('login.get_code') }}
              </button>
            </div>
          </div>
        </div>

        <!-- 创建密码区 -->
        <div class="section-block">
          <div class="section-heading">{{ t('register.create_pwd') }}</div>

          <div class="field-group">
            <label class="field-label">{{ t('login.password') }}</label>
            <div class="password-wrap">
              <input
                class="field-input"
                :class="{ error: errors.password }"
                :type="showPwd ? 'text' : 'password'"
                v-model="form.password"
                :placeholder="t('login.password')"
                maxlength="16"
                @input="checkPasswordRules"
              />
              <span class="pwd-eye" @click="showPwd = !showPwd">
                <svg v-if="showPwd" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#666" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
                </svg>
                <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#666" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/>
                  <line x1="1" y1="1" x2="23" y2="23"/>
                </svg>
              </span>
            </div>
          </div>

          <ul class="pwd-rules">
            <li :class="{ pass: pwdRules.length }">
              <span class="rule-dot"></span>
              {{ t('register.pwd_rule_length') }}
            </li>
            <li :class="{ pass: pwdRules.letter }">
              <span class="rule-dot"></span>
              {{ t('register.pwd_rule_letter') }}
            </li>
            <li :class="{ pass: pwdRules.number }">
              <span class="rule-dot"></span>
              {{ t('register.pwd_rule_number') }}
            </li>
          </ul>

          <div class="field-group">
            <label class="field-label">{{ t('register.confirm_pwd') }}</label>
            <div class="password-wrap">
              <input
                class="field-input"
                :class="{ error: errors.confirmPassword }"
                :type="showPwdConfirm ? 'text' : 'password'"
                v-model="form.confirmPassword"
                :placeholder="t('register.confirm_pwd')"
                maxlength="16"
              />
              <span class="pwd-eye" @click="showPwdConfirm = !showPwdConfirm">
                <svg v-if="showPwdConfirm" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#666" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
                </svg>
                <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#666" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/>
                  <line x1="1" y1="1" x2="23" y2="23"/>
                </svg>
              </span>
            </div>
            <div v-if="errors.confirmPassword" class="error-text">{{ errors.confirmPassword }}</div>
          </div>
        </div>

        <!-- 安全问题区 -->
        <div class="section-block">
          <div class="section-heading">{{ t('register.security_q') }}</div>
          <p class="section-desc">{{ t('register.security_q_desc') }}</p>
          <div class="field-group">
            <select class="field-input" v-model="form.securityQuestion">
              <option value="" disabled>{{ t('register.select_q') }}</option>
              <option value="pet">{{ t('register.q_pet') }}</option>
              <option value="school">{{ t('register.q_school') }}</option>
              <option value="city">{{ t('register.q_city') }}</option>
              <option value="book">{{ t('register.q_book') }}</option>
            </select>
          </div>
          <div class="field-group">
            <input class="field-input" v-model="form.securityAnswer" :placeholder="t('register.enter_answer')" />
          </div>
        </div>

        <!-- 联系方式区 -->
        <div class="section-block">
          <div class="section-heading">{{ t('register.contact_info') }}</div>
          <p class="section-desc">{{ t('register.contact_desc') }}</p>
          <div class="field-group">
            <label class="field-label">{{ t('register.email') }}</label>
            <input
              class="field-input"
              :class="{ error: errors.email }"
              type="email"
              v-model="form.email"
              :placeholder="t('register.email')"
            />
            <div v-if="errors.email" class="error-text">{{ errors.email }}</div>
          </div>
        </div>

        <!-- 声明区 -->
        <div class="section-block">
          <div class="section-heading">{{ t('register.declaration') }}</div>
          <p class="declaration-text">
            {{ t('register.declaration_text') }}
            <a href="javascript:;">{{ t('register.terms_link') }}</a>,
            <a href="javascript:;">{{ t('register.privacy_link') }}</a>,
            <a href="javascript:;">{{ t('register.terms_of_use') }}</a>.
          </p>
          <label class="checkbox-label">
            <input type="checkbox" v-model="form.marketingConsent" />
            <span>{{ t('register.marketing') }}</span>
          </label>
        </div>

        <!-- 已有账号 -->
        <div class="account-link">
          {{ t('register.have_account') }}
          <a @click="$router.push('/login')">{{ t('login.log_in') }} <span class="chevron">&rsaquo;</span></a>
        </div>

        <!-- 底部操作 -->
        <div class="action-row">
          <a class="back-link" @click="$router.push('/login')">
            <span class="chevron-back">&lsaquo;</span> {{ t('common.back') }}
          </a>
          <button class="btn-signup" :disabled="loading" @click="handleRegister">
            <span v-if="loading" class="loading-spinner"></span>
            <span v-else>{{ t('register.sign_up') }}</span>
          </button>
        </div>
      </div>

      <!-- 右侧图片 -->
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
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { sendSmsCode, register } from '../api/index.js'
import { validatePhone, validatePassword, validateEmail } from '../utils/validators.js'
import { useI18n } from '../utils/i18n.js'
import LangSwitcher from '../components/LangSwitcher.vue'

const router = useRouter()
const { t } = useI18n()
const langSwitcherRef = ref(null)
const loading = ref(false)
const showPwd = ref(false)
const showPwdConfirm = ref(false)
const countdown = ref(0)
const toast = ref(null)

const form = reactive({
  phone: '', code: '', password: '', confirmPassword: '',
  email: '', inviteCode: '',
  securityQuestion: '', securityAnswer: '',
  marketingConsent: false,
})
const errors = reactive({
  phone: '', password: '', confirmPassword: '', email: '',
})

const pwdRules = reactive({
  length: false,
  letter: false,
  number: false,
})

function checkPasswordRules() {
  const p = form.password
  pwdRules.length = p.length >= 8 && p.length <= 16
  pwdRules.letter = /[a-z]/.test(p) && /[A-Z]/.test(p)
  pwdRules.number = /\d/.test(p)
}

function showToast(msg, type = 'error') {
  toast.value = { msg, type }
  setTimeout(() => { toast.value = null }, 3000)
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

async function handleRegister() {
  errors.phone = validatePhone(form.phone)
  errors.password = validatePassword(form.password)
  errors.email = validateEmail(form.email)
  errors.confirmPassword = form.password !== form.confirmPassword ? t('register.pwd_mismatch') : ''

  if (!form.code || form.code.length !== 6) {
    showToast(t('login.enter_code'))
    return
  }
  if (errors.phone || errors.password || errors.confirmPassword || errors.email) return

  loading.value = true
  try {
    const res = await register({
      phone: form.phone,
      code: form.code,
      password: form.password,
      confirm_password: form.confirmPassword,
      email: form.email || undefined,
      invite_code: form.inviteCode || undefined,
    })
    if (res.code === 0) {
      showToast(t('register.success'), 'success')
      setTimeout(() => router.push('/login'), 1500)
    } else {
      showToast(res.message)
    }
  } catch (e) {
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
  font-family: 'Univers Next for HSBC', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
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
  padding: 40px 56px 32px;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}
.form-subtitle {
  font-size: 14px;
  color: #666;
  margin-bottom: 8px;
}
.form-title {
  font-size: 36px;
  font-weight: 300;
  color: #333;
  line-height: 1.25;
  margin-bottom: 36px;
  letter-spacing: -0.3px;
}

.section-block {
  border-left: 4px solid #DB0011;
  padding-left: 20px;
  margin-bottom: 32px;
}
.section-heading {
  font-size: 18px;
  font-weight: 600;
  color: #333;
  margin-bottom: 16px;
}
.section-desc {
  font-size: 13px;
  color: #666;
  line-height: 1.5;
  margin-bottom: 16px;
}

.field-group {
  margin-bottom: 16px;
}
.field-label {
  display: block;
  font-size: 14px;
  color: #333;
  margin-bottom: 6px;
  font-weight: 400;
}
.field-input {
  width: 100%;
  height: 44px;
  border: 1px solid #ccc;
  border-radius: 4px;
  padding: 0 12px;
  font-size: 14px;
  color: #333;
  outline: none;
  background: #fff;
  transition: border-color 0.2s;
}
.field-input:focus {
  border-color: #333;
}
.field-input.error {
  border-color: #DB0011;
}
select.field-input {
  appearance: auto;
  cursor: pointer;
  color: #333;
}
select.field-input option[value=""][disabled] {
  color: #999;
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
}
.phone-row .field-input {
  border-radius: 0 4px 4px 0;
}

.code-row {
  display: flex;
  gap: 12px;
}
.code-row .field-input {
  flex: 1;
}
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

.password-wrap {
  position: relative;
}
.pwd-eye {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  cursor: pointer;
  display: flex;
  align-items: center;
  padding: 4px;
}
.pwd-eye:hover svg {
  stroke: #DB0011;
}

.pwd-rules {
  list-style: none;
  padding: 0;
  margin: 0 0 20px 0;
}
.pwd-rules li {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #999;
  line-height: 1.8;
  transition: color 0.2s;
}
.pwd-rules li.pass {
  color: #00847F;
}
.rule-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  border: 1.5px solid #ccc;
  flex-shrink: 0;
  transition: all 0.2s;
}
.pwd-rules li.pass .rule-dot {
  border-color: #00847F;
  background: #00847F;
}

.declaration-text {
  font-size: 13px;
  color: #666;
  line-height: 1.6;
  margin-bottom: 16px;
}
.declaration-text a {
  color: #333;
  text-decoration: underline;
}
.declaration-text a:hover {
  color: #DB0011;
}
.checkbox-label {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
  color: #666;
  line-height: 1.5;
  cursor: pointer;
}
.checkbox-label input[type="checkbox"] {
  width: 16px;
  height: 16px;
  margin-top: 2px;
  accent-color: #DB0011;
  flex-shrink: 0;
}

.error-text {
  color: #DB0011;
  font-size: 12px;
  margin-top: 4px;
}

.account-link {
  font-size: 14px;
  color: #333;
  margin-bottom: 24px;
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
  padding-top: 20px;
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
.btn-signup {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 100px;
  height: 40px;
  padding: 0 28px;
  background: #DB0011;
  color: #fff;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s, box-shadow 0.2s;
}
.btn-signup:hover {
  background: #af000e;
  box-shadow: 0 2px 8px rgba(219, 0, 17, 0.3);
}
.btn-signup:disabled {
  background: #e8a0a0;
  cursor: not-allowed;
  box-shadow: none;
}

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
}
.chat-fab:hover { box-shadow: 0 6px 24px rgba(0,0,0,0.3); }
.chat-fab span {
  color: #fff;
  font-size: 11px;
  font-weight: 500;
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

@media (max-width: 899px) {
  .hsbc-form-area {
    flex: 1;
    max-width: 100%;
    padding: 24px 20px;
  }
  .form-title { font-size: 28px; }
  .hsbc-header { padding: 0 20px; }
  .hsbc-footer { padding: 16px 20px; }
}
</style>
