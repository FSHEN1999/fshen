<template>
  <div class="dashboard-page">
    <!-- 顶部红色导航 -->
    <header class="dash-header">
      <div class="dash-header-inner">
        <div class="dash-header-left">
          <svg width="40" height="28" viewBox="0 0 40 28" fill="none" class="header-logo-svg">
            <rect x="0.5" y="0.5" width="39" height="27" rx="3" stroke="rgba(255,255,255,0.3)" fill="none"/>
            <polygon points="8,6 20,14 8,22" fill="#fff"/>
            <polygon points="32,6 20,14 32,22" fill="#fff"/>
            <polygon points="8,6 32,6 20,14" fill="#DB0011"/>
            <polygon points="8,22 32,22 20,14" fill="#DB0011"/>
            <polygon points="8,6 20,6 20,14" fill="#fff"/>
            <polygon points="32,22 20,22 20,14" fill="#fff"/>
          </svg>
          <nav class="dash-nav">
            <a class="nav-item active">{{ t('dashboard.loan_app') }}</a>
            <a class="nav-item">{{ t('dashboard.loan_repay') }}</a>
            <a class="nav-item">{{ t('dashboard.account_settings') }}</a>
          </nav>
        </div>
        <div class="dash-header-right">
          <a class="logout-link" @click="handleLogout">{{ t('dashboard.log_out') }}</a>
        </div>
      </div>
    </header>

    <!-- 欢迎横幅 -->
    <div class="welcome-banner">
      <div class="welcome-inner">
        <h1 class="welcome-title">{{ t('dashboard.welcome') }}</h1>
        <p class="welcome-sub">{{ t('dashboard.last_login') }}: {{ lastLogin }}</p>
      </div>
    </div>

    <!-- 主要内容区 -->
    <div class="dash-content">
      <div class="dash-content-inner">
        <!-- 额度卡片 -->
        <div class="offer-card">
          <div class="offer-left">
            <!-- 贷款方 -->
            <div class="lender-info">
              <span class="lender-label">{{ t('dashboard.lending_providers') }}</span>
              <div class="lender-logos">
                <span class="lender-name">FundPark</span>
                <span class="lender-divider">|</span>
                <span class="lender-name">汇能贵诚信托</span>
              </div>
            </div>

            <!-- 预批额度 -->
            <div class="limit-section">
              <p class="limit-label">{{ t('dashboard.pre_approved') }}</p>
              <p class="limit-amount">{{ formatAmount(preApprovedLimit) }}</p>
            </div>

            <!-- 特点列表 -->
            <ul class="features-list">
              <li>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="8" fill="#DB0011"/><path d="M4.5 8L7 10.5L11.5 6" stroke="#fff" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
                {{ t('dashboard.feature_fast') }}
              </li>
              <li>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="8" fill="#DB0011"/><path d="M4.5 8L7 10.5L11.5 6" stroke="#fff" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
                {{ t('dashboard.feature_no_credit') }}
              </li>
              <li>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="8" fill="#DB0011"/><path d="M4.5 8L7 10.5L11.5 6" stroke="#fff" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
                {{ t('dashboard.feature_no_fee') }}
              </li>
            </ul>

            <p class="features-note">{{ t('dashboard.apply_note') }} {{ formatAmount(preApprovedLimit) }}</p>

            <!-- 申请按钮 -->
            <button class="btn-apply" @click="$router.push('/info')">{{ t('dashboard.apply_now') }}</button>
          </div>

          <!-- 右侧步骤 -->
          <div class="offer-right">
            <h3 class="steps-title">{{ t('dashboard.steps_title') }}</h3>
            <div class="step-item">
              <div class="step-number">1</div>
              <div class="step-content">
                <p class="step-name">{{ t('dashboard.step1_name') }}</p>
                <p class="step-desc">{{ t('dashboard.step1_desc') }}</p>
              </div>
            </div>
            <div class="step-item">
              <div class="step-number">2</div>
              <div class="step-content">
                <p class="step-name">{{ t('dashboard.step2_name') }}</p>
                <p class="step-desc">{{ t('dashboard.step2_desc') }}</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Before you apply 可展开区域 -->
        <div class="before-apply">
          <div class="accordion-item" v-for="(item, idx) in accordionItems" :key="idx">
            <button class="accordion-header" @click="toggleAccordion(idx)">
              <span>{{ item.title }}</span>
              <svg :class="{ rotated: item.open }" width="12" height="8" viewBox="0 0 12 8" fill="none">
                <path d="M1 1.5L6 6.5L11 1.5" stroke="#333" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </button>
            <div v-if="item.open" class="accordion-body">
              <p v-for="(line, li) in item.content" :key="li">{{ line }}</p>
            </div>
          </div>
        </div>

        <!-- 警告提示 -->
        <div class="borrow-warning">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <circle cx="10" cy="10" r="9" stroke="#DB0011" stroke-width="1.5"/>
            <line x1="10" y1="6" x2="10" y2="11" stroke="#DB0011" stroke-width="1.5" stroke-linecap="round"/>
            <circle cx="10" cy="14" r="1" fill="#DB0011"/>
          </svg>
          <span>{{ t('dashboard.borrow_warning') }}</span>
        </div>
      </div>
    </div>

    <!-- 底部页脚 -->
    <footer class="dash-footer">
      <div class="dash-footer-inner">
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
      </div>
    </footer>

    <LangSwitcher ref="langSwitcherRef" />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watchEffect } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import { useUserStore } from '../stores/user.js'
import { getQuota } from '../api/index.js'
import { useI18n } from '../utils/i18n.js'
import LangSwitcher from '../components/LangSwitcher.vue'

const router = useRouter()
const authStore = useAuthStore()
const userStore = useUserStore()
const { t } = useI18n()

const langSwitcherRef = ref(null)
const preApprovedLimit = ref(70000)
const lastLogin = ref('')

function formatAmount(num) {
  return Number(num).toLocaleString('en-US')
}

function handleLogout() {
  authStore.logout()
  userStore.reset()
  router.push('/login')
}

const accordionItems = reactive([
  { titleKey: 'dashboard.before_apply', contentKey: 'dashboard.acc_before', title: '', open: false, content: [] },
  { titleKey: 'dashboard.required_doc', contentKey: 'dashboard.acc_doc', title: '', open: false, content: [] },
  { titleKey: 'dashboard.eligibility', contentKey: 'dashboard.acc_elig', title: '', open: false, content: [] },
  { titleKey: 'dashboard.product_info', contentKey: 'dashboard.acc_product', title: '', open: false, content: [] },
])

// 监听语言变化，更新手风琴内容
watchEffect(() => {
  for (const item of accordionItems) {
    item.title = t(item.titleKey)
    item.content = t(item.contentKey)
  }
})

function toggleAccordion(idx) {
  accordionItems[idx].open = !accordionItems[idx].open
}

onMounted(async () => {
  const now = new Date()
  lastLogin.value = now.toLocaleDateString('en-US', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })

  try {
    const res = await getQuota()
    if (res.code === 0 && res.data?.estimated_quota) {
      preApprovedLimit.value = res.data.estimated_quota
    }
  } catch {}
})
</script>

<style scoped>
.dashboard-page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: #f5f5f5;
  font-family: 'Univers Next for HSBC', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

/* 红色顶部导航 */
.dash-header {
  background: #DB0011;
  height: 56px;
  flex-shrink: 0;
}
.dash-header-inner {
  max-width: 1200px;
  margin: 0 auto;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 32px;
}
.dash-header-left {
  display: flex;
  align-items: center;
  gap: 32px;
}
.header-logo-svg {
  flex-shrink: 0;
}
.dash-nav {
  display: flex;
  gap: 4px;
}
.nav-item {
  padding: 8px 16px;
  font-size: 14px;
  color: rgba(255,255,255,0.85);
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.2s;
  text-decoration: none;
}
.nav-item:hover {
  background: rgba(255,255,255,0.15);
  color: #fff;
}
.nav-item.active {
  background: rgba(255,255,255,0.2);
  color: #fff;
  font-weight: 500;
}
.logout-link {
  font-size: 14px;
  color: rgba(255,255,255,0.85);
  cursor: pointer;
  text-decoration: underline;
}
.logout-link:hover {
  color: #fff;
}

/* 欢迎横幅 */
.welcome-banner {
  background: #333;
  padding: 40px 0;
}
.welcome-inner {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 32px;
}
.welcome-title {
  font-size: 32px;
  font-weight: 300;
  color: #fff;
  margin-bottom: 8px;
}
.welcome-sub {
  font-size: 14px;
  color: rgba(255,255,255,0.6);
}

/* 主内容 */
.dash-content {
  flex: 1;
  padding: 32px 0;
}
.dash-content-inner {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 32px;
}

/* 额度卡片 */
.offer-card {
  display: flex;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
  overflow: hidden;
  margin-bottom: 24px;
}
.offer-left {
  flex: 1;
  padding: 32px 40px;
}
.offer-right {
  width: 320px;
  background: #f8f9fa;
  padding: 32px;
  border-left: 1px solid #eee;
}

/* 贷款方信息 */
.lender-info {
  margin-bottom: 24px;
}
.lender-label {
  font-size: 12px;
  color: #999;
  display: block;
  margin-bottom: 6px;
}
.lender-logos {
  display: flex;
  align-items: center;
  gap: 8px;
}
.lender-name {
  font-size: 14px;
  color: #333;
  font-weight: 500;
}
.lender-divider {
  color: #ddd;
}

/* 额度展示 */
.limit-section {
  margin-bottom: 24px;
}
.limit-label {
  font-size: 14px;
  color: #666;
  margin-bottom: 4px;
}
.limit-amount {
  font-size: 48px;
  font-weight: 700;
  color: #333;
  letter-spacing: -1px;
}

/* 特点列表 */
.features-list {
  list-style: none;
  padding: 0;
  margin: 0 0 12px 0;
}
.features-list li {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  color: #333;
  line-height: 2;
}
.features-note {
  font-size: 12px;
  color: #999;
  margin-bottom: 24px;
}

/* 申请按钮 */
.btn-apply {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 180px;
  height: 44px;
  padding: 0 32px;
  background: #DB0011;
  color: #fff;
  border: none;
  border-radius: 4px;
  font-size: 16px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s, box-shadow 0.2s;
}
.btn-apply:hover {
  background: #af000e;
  box-shadow: 0 2px 8px rgba(219, 0, 17, 0.3);
}

/* 右侧步骤 */
.steps-title {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  margin-bottom: 24px;
}
.step-item {
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
}
.step-number {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #DB0011;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
}
.step-name {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 4px;
}
.step-desc {
  font-size: 13px;
  color: #999;
}

/* 手风琴 */
.before-apply {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
  margin-bottom: 24px;
  overflow: hidden;
}
.accordion-header {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: none;
  border: none;
  border-bottom: 1px solid #eee;
  font-size: 14px;
  font-weight: 500;
  color: #333;
  cursor: pointer;
  text-align: left;
  transition: background 0.2s;
}
.accordion-header:hover {
  background: #f8f9fa;
}
.accordion-header svg {
  transition: transform 0.2s;
  flex-shrink: 0;
}
.accordion-header svg.rotated {
  transform: rotate(180deg);
}
.accordion-body {
  padding: 16px 24px;
  border-bottom: 1px solid #eee;
}
.accordion-body p {
  font-size: 13px;
  color: #666;
  line-height: 1.8;
}

/* 风险提示 */
.borrow-warning {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 24px;
  background: #fff;
  border-radius: 8px;
  border-left: 4px solid #DB0011;
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
}
.borrow-warning span {
  font-size: 14px;
  color: #333;
  font-weight: 500;
}

/* 页脚 */
.dash-footer {
  border-top: 1px solid #ddd;
  background: #fff;
  padding: 20px 0;
  flex-shrink: 0;
}
.dash-footer-inner {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 32px;
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

/* 移动端适配 */
@media (max-width: 899px) {
  .offer-card {
    flex-direction: column;
  }
  .offer-right {
    width: 100%;
    border-left: none;
    border-top: 1px solid #eee;
  }
  .dash-nav { display: none; }
  .welcome-title { font-size: 24px; }
  .limit-amount { font-size: 36px; }
  .dash-header-inner,
  .welcome-inner,
  .dash-content-inner,
  .dash-footer-inner {
    padding: 0 16px;
  }
}
</style>
