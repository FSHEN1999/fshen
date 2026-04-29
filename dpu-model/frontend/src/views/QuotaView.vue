<template>
  <div class="page-container quota-page">
    <!-- 加载中 -->
    <div v-if="loading" class="loading-state">
      <div class="loading-spinner big"></div>
      <p>{{ t('quota.calculating') }}</p>
    </div>

    <!-- 高风险拦截 -->
    <div v-else-if="blocked" class="blocked-state">
      <div class="status-icon rejected">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#DB0011" stroke-width="2" stroke-linecap="round">
          <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
        </svg>
      </div>
      <h2 class="status-text">{{ t('quota.blocked') }}</h2>
      <p class="status-note">{{ blockMsg }}</p>
      <button class="btn-secondary" @click="$router.push('/info')" style="margin-top: 24px;">{{ t('quota.improve_info') }}</button>
    </div>

    <!-- 额度展示 -->
    <div v-else-if="quota" class="quota-result">
      <p class="quota-label">{{ t('quota.your_limit') }}</p>

      <div class="quota-amount-wrap">
        <span class="quota-currency">¥</span>
        <span class="quota-amount">{{ formatAmount(quota.estimated_quota) }}</span>
      </div>

      <p class="quota-basis">{{ quota.assessment_basis }}</p>

      <div class="quota-details">
        <div class="detail-item">
          <span class="detail-label">{{ t('quota.repay_period') }}</span>
          <span class="detail-value">{{ quota.suggested_period }}{{ t('quota.months') }}</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">{{ t('quota.annual_rate') }}</span>
          <span class="detail-value">{{ (quota.interest_rate * 100).toFixed(1) }}%</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">{{ t('quota.risk_level') }}</span>
          <span class="detail-value" :class="'risk-' + quota.risk_level">{{ quota.risk_level }}{{ t('quota.risk_suffix') }}</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">{{ t('quota.valid_until') }}</span>
          <span class="detail-value">{{ quota.valid_until }}</span>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="action-buttons">
        <button class="btn-primary" :disabled="applying" @click="handleApply">
          <span v-if="applying" class="loading-spinner"></span>
          <span v-else>{{ t('quota.apply_loan') }}</span>
        </button>
        <button class="btn-secondary" @click="refreshQuota">{{ t('quota.recalculate') }}</button>
        <a class="link-back" @click="$router.back()">{{ t('quota.go_back') }}</a>
      </div>
    </div>

    <!-- 无数据 -->
    <div v-else class="empty-state">
      <p>{{ t('quota.fill_first') }}</p>
      <button class="btn-primary" @click="$router.push('/info')" style="margin-top: 16px; max-width: 200px;">{{ t('quota.go_fill') }}</button>
    </div>

    <div v-if="toast" :class="['toast', toast.type]">{{ toast.msg }}</div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getQuota, applyLoan } from '../api/index.js'
import { useI18n } from '../utils/i18n.js'

const { t } = useI18n()
const router = useRouter()
const loading = ref(true)
const applying = ref(false)
const quota = ref(null)
const blocked = ref(false)
const blockMsg = ref('')
const toast = ref(null)

function formatAmount(num) {
  return Number(num).toLocaleString('zh-CN', { maximumFractionDigits: 0 })
}

function showToast(msg, type = 'error') {
  toast.value = { msg, type }
  setTimeout(() => { toast.value = null }, 3000)
}

async function fetchQuota() {
  loading.value = true
  blocked.value = false
  try {
    const res = await getQuota()
    if (res.code === 0) {
      quota.value = res.data
    } else if (res.code === 403) {
      blocked.value = true
      blockMsg.value = res.data?.risk_note || res.message
    } else {
      showToast(res.message)
    }
  } catch (e) {
    showToast(t('common.network_error'))
  } finally {
    loading.value = false
  }
}

function refreshQuota() {
  quota.value = null
  fetchQuota()
}

async function handleApply() {
  if (!quota.value) return
  applying.value = true
  try {
    const res = await applyLoan({
      loan_amount: quota.value.estimated_quota,
      loan_purpose: '经营周转',
    })
    if (res.code === 0) {
      showToast(t('quota.applied'), 'success')
      setTimeout(() => router.push('/approval'), 800)
    } else {
      showToast(res.message)
    }
  } catch {
    showToast(t('common.network_error'))
  } finally {
    applying.value = false
  }
}

onMounted(fetchQuota)
</script>

<style scoped>
.quota-page {
  text-align: center;
  padding-top: 48px;
  max-width: 600px;
}

.loading-state {
  padding-top: 80px;
  color: #999;
}
.loading-spinner.big {
  width: 36px;
  height: 36px;
  border: 3px solid #DB0011;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
  margin: 0 auto 16px;
}

.blocked-state {
  padding-top: 40px;
}
.status-icon.rejected {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: #fef0f0;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
}
.status-text {
  font-size: 20px;
  font-weight: 400;
  color: #333;
  margin-bottom: 8px;
}
.status-note {
  color: #999;
  font-size: 14px;
}

.quota-result {
  padding-top: 20px;
}
.quota-label {
  font-size: 16px;
  color: #666;
  margin-bottom: 16px;
}
.quota-amount-wrap {
  margin-bottom: 8px;
}
.quota-currency {
  font-size: 28px;
  color: #DB0011;
  font-weight: 600;
  vertical-align: top;
  line-height: 1.4;
}
.quota-amount {
  font-size: 52px;
  color: #DB0011;
  font-weight: 700;
  letter-spacing: -1px;
}
.quota-basis {
  font-size: 12px;
  color: #999;
  margin-bottom: 28px;
}

.quota-details {
  background: #f8f9fa;
  border: 1px solid #eee;
  border-radius: 4px;
  padding: 4px 20px;
  text-align: left;
  margin-bottom: 32px;
}
.detail-item {
  display: flex;
  justify-content: space-between;
  padding: 12px 0;
  border-bottom: 1px solid #eee;
}
.detail-item:last-child { border-bottom: none; }
.detail-label { color: #999; font-size: 14px; }
.detail-value { color: #333; font-size: 14px; font-weight: 500; }
.risk-低 { color: #00847F; }
.risk-中 { color: #FF9F0A; }
.risk-高 { color: #DB0011; }

.action-buttons {
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: center;
}
.link-back {
  font-size: 13px;
  color: #333;
  cursor: pointer;
  text-decoration: underline;
  margin-top: 4px;
}
.link-back:hover { color: #DB0011; }

.empty-state {
  padding-top: 80px;
  color: #999;
}
</style>
