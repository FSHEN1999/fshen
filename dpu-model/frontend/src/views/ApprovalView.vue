<template>
  <div class="approval-page">
    <div class="page-body">
      <div class="page-body-inner">
        <h1 class="page-title">{{ t('approval.title') }}</h1>

        <!-- 加载中 -->
        <div v-if="loading" class="loading-state">
          <div class="loading-spinner big"></div>
          <p>{{ t('common.loading') }}</p>
        </div>

        <!-- 审批状态 -->
        <div v-else-if="approval" class="status-section">
          <!-- 状态卡片 -->
          <div class="status-card">
            <!-- 状态图标 -->
            <div class="status-icon" :class="statusClass">
              <svg v-if="approval.status === 'approved'" width="36" height="36" viewBox="0 0 36 36" fill="none">
                <circle cx="18" cy="18" r="17" fill="#00847F"/>
                <path d="M10 18L16 24L26 14" stroke="#fff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
              <svg v-else-if="approval.status === 'rejected'" width="36" height="36" viewBox="0 0 36 36" fill="none">
                <circle cx="18" cy="18" r="17" fill="#DB0011"/>
                <path d="M12 12L24 24M24 12L12 24" stroke="#fff" stroke-width="2.5" stroke-linecap="round"/>
              </svg>
              <svg v-else width="36" height="36" viewBox="0 0 36 36" fill="none">
                <circle cx="18" cy="18" r="17" fill="#0073CF"/>
                <circle cx="18" cy="18" r="10" stroke="#fff" stroke-width="1.5" fill="none"/>
                <path d="M18 12V18L22 20" stroke="#fff" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </div>

            <h2 class="status-label" :style="{ color: statusColor }">{{ statusText }}</h2>
            <p class="status-desc">{{ statusDesc }}</p>

            <!-- 驳回原因 -->
            <div v-if="approval.reject_reason" class="reject-box">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <circle cx="8" cy="8" r="7" stroke="#DB0011" stroke-width="1.2"/>
                <line x1="8" y1="5" x2="8" y2="9" stroke="#DB0011" stroke-width="1.2" stroke-linecap="round"/>
                <circle cx="8" cy="11.5" r="0.7" fill="#DB0011"/>
              </svg>
              <span>{{ approval.reject_reason }}</span>
            </div>

            <!-- 申请详情 -->
            <div class="detail-card">
              <div class="detail-row">
                <span class="detail-label">{{ t('approval.app_id') }}</span>
                <span class="detail-value">{{ approval.application_id || 'DPU-' + (approval.id || '000001') }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">{{ t('approval.submitted_on') }}</span>
                <span class="detail-value">{{ formatDate(approval.created_at) }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">{{ t('approval.loan_amount') }}</span>
                <span class="detail-value">{{ approval.loan_amount ? Number(approval.loan_amount).toLocaleString() : '-' }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">{{ t('approval.lending_provider') }}</span>
                <span class="detail-value">FundPark</span>
              </div>
            </div>

            <!-- 操作 -->
            <div class="card-actions">
              <a class="link-refresh" @click="refreshStatus">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M1 7a6 6 0 1011.2-3" stroke="#333" stroke-width="1.2" stroke-linecap="round"/>
                  <path d="M12.2 1v3h-3" stroke="#333" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                {{ t('approval.refresh') }}
              </a>
              <button v-if="approval.status === 'assessing'" class="btn-cancel" @click="handleCancel">{{ t('approval.cancel_app') }}</button>
              <button v-if="approval.status === 'rejected'" class="btn-resubmit" @click="$router.push('/info')">{{ t('approval.resubmit') }}</button>
            </div>
          </div>

          <!-- 进度时间线 -->
          <div class="timeline">
            <div class="timeline-step" :class="{ done: true }">
              <div class="step-dot done">
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M2 6L5 9L10 3" stroke="#fff" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
              </div>
              <span class="step-label">{{ t('approval.submitted') }}</span>
            </div>
            <div class="timeline-line" :class="{ active: approval.status !== 'assessing' || true }"></div>
            <div class="timeline-step" :class="{ active: approval.status === 'assessing', done: approval.status === 'approved' || approval.status === 'rejected' }">
              <div class="step-dot" :class="{ active: approval.status === 'assessing', done: approval.status === 'approved' || approval.status === 'rejected' }">
                <svg v-if="approval.status === 'approved' || approval.status === 'rejected'" width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M2 6L5 9L10 3" stroke="#fff" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
              </div>
              <span class="step-label">{{ t('approval.under_review') }}</span>
            </div>
            <div class="timeline-line" :class="{ active: approval.status === 'approved' || approval.status === 'rejected' }"></div>
            <div class="timeline-step" :class="{ done: approval.status === 'approved', rejected: approval.status === 'rejected' }">
              <div class="step-dot" :class="{ done: approval.status === 'approved', rejected: approval.status === 'rejected' }">
                <svg v-if="approval.status === 'approved'" width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M2 6L5 9L10 3" stroke="#fff" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                <svg v-else-if="approval.status === 'rejected'" width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M3 3L9 9M9 3L3 9" stroke="#fff" stroke-width="1.5" stroke-linecap="round"/>
                </svg>
              </div>
              <span class="step-label">{{ t('approval.result') }}</span>
            </div>
          </div>

          <!-- 返回 -->
          <div class="back-link-wrap">
            <a class="back-link" @click="$router.push('/dashboard')">{{ t('approval.back_dash') }}</a>
          </div>
        </div>

        <!-- 无申请 -->
        <div v-else class="empty-state">
          <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
            <circle cx="24" cy="24" r="22" stroke="#ccc" stroke-width="1.5"/>
            <path d="M16 24h16M24 16v16" stroke="#ccc" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
          <p>{{ t('approval.no_app') }}</p>
          <button class="btn-dashboard" @click="$router.push('/dashboard')">{{ t('approval.back_dashboard') }}</button>
        </div>
      </div>
    </div>

    <!-- 取消确认弹窗 -->
    <div v-if="showCancelDialog" class="dialog-overlay" @click="showCancelDialog = false">
      <div class="dialog-box" @click.stop>
        <h3>{{ t('approval.cancel_title') }}</h3>
        <p class="dialog-desc">{{ t('approval.cancel_desc') }}</p>
        <div class="dialog-actions">
          <button class="dialog-btn secondary" @click="showCancelDialog = false">{{ t('approval.go_back') }}</button>
          <button class="dialog-btn primary" @click="confirmCancel">{{ t('approval.confirm_cancel') }}</button>
        </div>
      </div>
    </div>

    <!-- 页脚 -->
    <footer class="page-footer">
      <div class="footer-inner">
        <div class="footer-links">
          <a>{{ t('footer.about') }}</a>
          <a>{{ t('footer.terms') }}</a>
          <a>{{ t('footer.privacy') }}</a>
          <a>{{ t('footer.hyperlink') }}</a>
        </div>
        <p class="footer-copyright">{{ t('footer.copyright') }}</p>
      </div>
    </footer>

    <div v-if="toast" :class="['toast', toast.type]">{{ toast.msg }}</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { getApprovalStatus, cancelApproval } from '../api/index.js'
import { useI18n } from '../utils/i18n.js'

const { t } = useI18n()
const loading = ref(true)
const approval = ref(null)
const showCancelDialog = ref(false)
const toast = ref(null)
let pollTimer = null

const statusClass = computed(() => {
  const s = approval.value?.status
  if (s === 'approved') return 'approved'
  if (s === 'rejected') return 'rejected'
  return 'assessing'
})
const statusColor = computed(() => {
  const s = approval.value?.status
  if (s === 'approved') return '#00847F'
  if (s === 'rejected') return '#DB0011'
  return '#0073CF'
})
const statusText = computed(() => {
  const s = approval.value?.status
  if (s === 'approved') return t('approval.approved')
  if (s === 'rejected') return t('approval.rejected')
  return t('approval.assessing')
})
const statusDesc = computed(() => {
  const s = approval.value?.status
  if (s === 'approved') return t('approval.approved_desc')
  if (s === 'rejected') return t('approval.rejected_desc')
  return t('approval.assessing_desc')
})

function formatDate(d) {
  if (!d) return '-'
  try {
    return new Date(d).toLocaleDateString('en-US', { day: '2-digit', month: 'short', year: 'numeric' })
  } catch { return d }
}

function showToast(msg, type = 'error') {
  toast.value = { msg, type }
  setTimeout(() => { toast.value = null }, 3000)
}

async function fetchStatus() {
  try {
    const res = await getApprovalStatus()
    if (res.code === 0) {
      approval.value = res.data
      if (res.data.status === 'approved' || res.data.status === 'rejected') {
        clearInterval(pollTimer)
        pollTimer = null
      }
    } else if (res.code === 404) {
      approval.value = null
    } else {
      showToast(res.message)
    }
  } catch {
    showToast(t('common.network_error'))
  } finally {
    loading.value = false
  }
}

function refreshStatus() {
  loading.value = true
  fetchStatus()
}

function handleCancel() { showCancelDialog.value = true }

async function confirmCancel() {
  showCancelDialog.value = false
  try {
    const res = await cancelApproval()
    if (res.code === 0) {
      showToast(t('approval.cancelled'), 'success')
      fetchStatus()
    } else {
      showToast(res.message)
    }
  } catch {
    showToast(t('approval.op_failed'))
  }
}

onMounted(() => {
  fetchStatus()
  pollTimer = setInterval(fetchStatus, 10000)
})
onUnmounted(() => { clearInterval(pollTimer) })
</script>

<style scoped>
.approval-page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: #f5f5f5;
  font-family: 'Univers Next for HSBC', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

.page-body {
  flex: 1;
  padding: 32px 0 48px;
}
.page-body-inner {
  max-width: 640px;
  margin: 0 auto;
  padding: 0 32px;
}
.page-title {
  font-size: 32px;
  font-weight: 300;
  color: #333;
  margin-bottom: 32px;
}

/* 加载 */
.loading-state {
  text-align: center;
  padding-top: 60px;
  color: #999;
}
.loading-spinner.big {
  width: 36px;
  height: 36px;
  border: 3px solid #0073CF;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
  margin: 0 auto 16px;
}

/* 状态卡片 */
.status-card {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
  padding: 40px 32px;
  text-align: center;
  margin-bottom: 24px;
}
.status-icon {
  margin-bottom: 16px;
}
.status-label {
  font-size: 24px;
  font-weight: 400;
  margin-bottom: 8px;
}
.status-desc {
  font-size: 14px;
  color: #666;
  line-height: 1.6;
  margin-bottom: 28px;
}

/* 驳回原因 */
.reject-box {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  background: #fff0f0;
  border: 1px solid #ffccc7;
  border-radius: 4px;
  padding: 12px 16px;
  text-align: left;
  margin-bottom: 24px;
}
.reject-box svg { flex-shrink: 0; margin-top: 1px; }
.reject-box span {
  font-size: 13px;
  color: #DB0011;
  line-height: 1.5;
}

/* 详情卡片 */
.detail-card {
  background: #f8f9fa;
  border: 1px solid #eee;
  border-radius: 4px;
  padding: 0 20px;
  text-align: left;
  margin-bottom: 24px;
}
.detail-row {
  display: flex;
  justify-content: space-between;
  padding: 14px 0;
  border-bottom: 1px solid #eee;
  font-size: 14px;
}
.detail-row:last-child { border-bottom: none; }
.detail-label { color: #999; }
.detail-value { color: #333; font-weight: 500; }

/* 操作 */
.card-actions {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}
.link-refresh {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  color: #333;
  cursor: pointer;
  text-decoration: underline;
}
.link-refresh:hover { color: #DB0011; }
.btn-cancel {
  width: 100%;
  height: 44px;
  background: #fff;
  color: #DB0011;
  border: 1px solid #DB0011;
  border-radius: 4px;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.2s;
}
.btn-cancel:hover { background: #fef0f0; }
.btn-resubmit {
  width: 100%;
  height: 44px;
  background: #DB0011;
  color: #fff;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
}
.btn-resubmit:hover { background: #af000e; }

/* 时间线 */
.timeline {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  margin-bottom: 32px;
}
.timeline-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}
.step-dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #e5e5e5;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s;
}
.step-dot.done {
  background: #00847F;
}
.step-dot.active {
  background: #0073CF;
  box-shadow: 0 0 0 4px rgba(0, 115, 207, 0.2);
}
.step-dot.rejected {
  background: #DB0011;
}
.step-label {
  font-size: 12px;
  color: #999;
  white-space: nowrap;
}
.timeline-step.done .step-label,
.timeline-step.active .step-label {
  color: #333;
  font-weight: 500;
}
.timeline-step.rejected .step-label {
  color: #DB0011;
  font-weight: 500;
}
.timeline-line {
  width: 80px;
  height: 3px;
  background: #e5e5e5;
  margin: 0 4px;
  margin-bottom: 24px;
  border-radius: 2px;
  transition: background 0.3s;
}
.timeline-line.active {
  background: #00847F;
}

/* 返回链接 */
.back-link-wrap {
  text-align: center;
}
.back-link {
  font-size: 14px;
  color: #333;
  text-decoration: underline;
  cursor: pointer;
}
.back-link:hover { color: #DB0011; }

/* 空状态 */
.empty-state {
  text-align: center;
  padding-top: 80px;
}
.empty-state p {
  font-size: 16px;
  color: #999;
  margin-top: 16px;
  margin-bottom: 20px;
}
.btn-dashboard {
  padding: 10px 24px;
  background: #DB0011;
  color: #fff;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  cursor: pointer;
}
.btn-dashboard:hover { background: #af000e; }

/* 弹窗 */
.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}
.dialog-box {
  background: #fff;
  border-radius: 8px;
  padding: 32px;
  width: 360px;
  text-align: center;
}
.dialog-box h3 {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 8px;
  color: #333;
}
.dialog-desc {
  font-size: 14px;
  color: #666;
  margin-bottom: 24px;
  line-height: 1.5;
}
.dialog-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}
.dialog-btn {
  padding: 0 24px;
  height: 40px;
  border-radius: 4px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}
.dialog-btn.secondary {
  background: #fff;
  color: #333;
  border: 1px solid #ccc;
}
.dialog-btn.secondary:hover { border-color: #333; }
.dialog-btn.primary {
  background: #DB0011;
  color: #fff;
  border: none;
}
.dialog-btn.primary:hover { background: #af000e; }

/* 页脚 */
.page-footer {
  background: #fff;
  border-top: 1px solid #ddd;
  padding: 20px 0;
}
.footer-inner {
  max-width: 640px;
  margin: 0 auto;
  padding: 0 32px;
}
.footer-links {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  margin-bottom: 12px;
}
.footer-links a {
  font-size: 12px;
  color: #333;
  cursor: pointer;
}
.footer-links a:hover { text-decoration: underline; }
.footer-copyright {
  font-size: 11px;
  color: #888;
  text-align: right;
}

/* Toast */
.toast {
  position: fixed;
  top: 80px;
  left: 50%;
  transform: translateX(-50%);
  padding: 12px 28px;
  border-radius: 4px;
  font-size: 14px;
  z-index: 2000;
  animation: fadeIn 0.2s;
}
.toast.error {
  background: #fff0f0;
  color: #DB0011;
  border: 1px solid #DB0011;
}
.toast.success {
  background: #f0fff4;
  color: #00847F;
  border: 1px solid #00847F;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateX(-50%) translateY(-10px); }
  to { opacity: 1; transform: translateX(-50%) translateY(0); }
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 移动端 */
@media (max-width: 768px) {
  .page-body-inner, .footer-inner {
    padding: 0 16px;
  }
  .page-title { font-size: 24px; }
  .status-card { padding: 28px 20px; }
  .timeline-line { width: 40px; }
}
</style>
