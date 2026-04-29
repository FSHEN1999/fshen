<template>
  <div class="info-page">
    <!-- 进度条 -->
    <div class="progress-bar-wrap">
      <div class="progress-bar-inner">
        <span class="progress-text">{{ t('info.progress') }}</span>
        <div class="progress-track">
          <div class="progress-fill" style="width: 50%"></div>
        </div>
      </div>
    </div>

    <div class="page-body">
      <div class="page-body-inner">
        <h1 class="page-title">{{ t('info.title') }}</h1>
        <p class="page-subtitle">{{ t('info.subtitle') }}</p>

        <p class="contact-link">{{ t('info.contact_us') }} <a>{{ t('info.contact_link') }}</a></p>
        <div class="privacy-note">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <circle cx="8" cy="8" r="7" stroke="#999" stroke-width="1.2"/>
            <line x1="8" y1="7" x2="8" y2="11" stroke="#999" stroke-width="1.2" stroke-linecap="round"/>
            <circle cx="8" cy="5" r="0.8" fill="#999"/>
          </svg>
          <span>{{ t('info.privacy') }}</span>
        </div>

        <!-- 注册信息 -->
        <div class="section-block">
          <h3 class="section-heading">{{ t('info.reg_info') }}</h3>
          <div class="section-body">
            <div class="field-row">
              <label class="field-label required">{{ t('info.company_cn') }}</label>
              <input class="field-input" :class="{ error: errors.company_name_cn }" v-model="form.company_name_cn" :placeholder="t('info.enter_cn')" />
              <div v-if="errors.company_name_cn" class="error-text">{{ errors.company_name_cn }}</div>
            </div>
            <div class="field-row">
              <label class="field-label">{{ t('info.company_en') }}</label>
              <input class="field-input" v-model="form.company_name_en" :placeholder="t('info.enter_en')" />
            </div>
            <div class="field-row">
              <label class="field-label required">{{ t('info.credit_code') }}</label>
              <input class="field-input" :class="{ error: errors.credit_code }" v-model="form.credit_code" :placeholder="t('info.enter_credit')" maxlength="18" />
              <div v-if="errors.credit_code" class="error-text">{{ errors.credit_code }}</div>
            </div>
          </div>
        </div>

        <!-- 经营信息 -->
        <div class="section-block">
          <h3 class="section-heading">{{ t('info.biz_ops') }}</h3>
          <div class="section-body">
            <p class="section-note">{{ t('info.biz_note') }}</p>

            <div class="field-row">
              <label class="field-label">{{ t('info.cust_countries') }}</label>
              <div class="tag-selector">
                <span v-for="tag in countryOptions" :key="'cust-'+tag"
                  class="tag-item" :class="{ active: form.customer_countries.includes(tag) }"
                  @click="toggleTag('customer_countries', tag, 3)">
                  {{ tag }}
                </span>
              </div>
            </div>

            <div class="field-row">
              <label class="field-label">{{ t('info.supp_countries') }}</label>
              <div class="tag-selector">
                <span v-for="tag in countryOptions" :key="'supp-'+tag"
                  class="tag-item" :class="{ active: form.supplier_countries.includes(tag) }"
                  @click="toggleTag('supplier_countries', tag, 3)">
                  {{ tag }}
                </span>
              </div>
            </div>

            <div class="field-row">
              <label class="field-label">{{ t('info.funding_country') }}</label>
              <select class="field-input" v-model="form.funding_country">
                <option value="" disabled>{{ t('info.select_country') }}</option>
                <option v-for="c in countryOptions" :key="c" :value="c">{{ c }}</option>
              </select>
            </div>

            <div class="field-row">
              <label class="field-label">{{ t('info.industry') }}</label>
              <select class="field-input" v-model="form.industry">
                <option value="" disabled>{{ t('info.select_industry') }}</option>
                <option v-for="ind in industryOptions" :key="ind" :value="ind">{{ ind }}</option>
              </select>
            </div>

            <div class="field-row">
              <label class="field-label">{{ t('info.main_products') }}</label>
              <textarea class="field-input field-textarea" v-model="form.main_products" :placeholder="t('info.describe_products')" rows="3"></textarea>
            </div>

            <div class="field-row">
              <label class="field-label">{{ t('info.initial_wealth') }}</label>
              <div class="checkbox-group">
                <label v-for="opt in wealthSourceOptions" :key="'isw-'+opt" class="checkbox-label">
                  <input type="checkbox" :value="opt" v-model="form.initial_wealth" />
                  <span class="checkbox-custom"></span>
                  <span>{{ opt }}</span>
                </label>
              </div>
            </div>

            <div class="field-row">
              <label class="field-label">{{ t('info.ongoing_income') }}</label>
              <div class="checkbox-group">
                <label v-for="opt in ongoingIncomeOptions" :key="'oi-'+opt" class="checkbox-label">
                  <input type="checkbox" :value="opt" v-model="form.ongoing_income" />
                  <span class="checkbox-custom"></span>
                  <span>{{ opt }}</span>
                </label>
              </div>
            </div>

            <div class="field-row">
              <label class="field-label">{{ t('info.fund_sources') }}</label>
              <div class="checkbox-group">
                <label v-for="opt in fundSourceOptions" :key="'fs-'+opt" class="checkbox-label">
                  <input type="checkbox" :value="opt" v-model="form.fund_sources" />
                  <span class="checkbox-custom"></span>
                  <span>{{ opt }}</span>
                </label>
              </div>
            </div>
          </div>
        </div>

        <!-- 声明 -->
        <div class="declaration-block">
          <p>{{ t('info.declaration') }}</p>
        </div>
      </div>
    </div>

    <!-- 固定底部操作栏 -->
    <div class="bottom-bar">
      <div class="bottom-bar-inner">
        <div class="bottom-bar-left">
          <a class="bar-link" @click="$router.push('/dashboard')">{{ t('common.back') }}</a>
          <a class="bar-link" @click="handleSave">{{ t('common.save_exit') }}</a>
        </div>
        <button class="btn-next" :disabled="loading" @click="handleSubmit">
          <span v-if="loading" class="loading-spinner"></span>
          <span v-else>{{ t('common.next') }}</span>
        </button>
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
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import { getProfile, submitProfile } from '../api/index.js'
import { useI18n } from '../utils/i18n.js'

const router = useRouter()
const authStore = useAuthStore()
const { t } = useI18n()
const loading = ref(false)
const toast = ref(null)

const countryOptions = ['China', 'Hong Kong', 'United States', 'Canada', 'United Kingdom', 'Japan', 'Singapore', 'Australia', 'Germany', 'France']
const industryOptions = ['Consumer Electronics', 'Fashion & Apparel', 'Home & Garden', 'Health & Beauty', 'Food & Beverage', 'Industrial Equipment', 'Technology', 'Automotive', 'Other']
const wealthSourceOptions = ['Business income', 'Savings', 'Inheritance', 'Gift', 'Other']
const ongoingIncomeOptions = ['Business income', 'Employment income', 'Investments', 'Rental income', 'Other']
const fundSourceOptions = ['Business revenue', 'Personal savings', 'Loans from financial institutions', 'Investment returns', 'Other']

const form = reactive({
  company_name_cn: '',
  company_name_en: '',
  credit_code: '',
  customer_countries: ['Hong Kong', 'United States', 'Canada'],
  supplier_countries: ['China'],
  funding_country: 'China',
  industry: 'Consumer Electronics',
  main_products: '',
  initial_wealth: [],
  ongoing_income: [],
  fund_sources: [],
})

const errors = reactive({
  company_name_cn: '',
  credit_code: '',
})

function toggleTag(field, tag, max) {
  const arr = form[field]
  const idx = arr.indexOf(tag)
  if (idx >= 0) {
    arr.splice(idx, 1)
  } else if (arr.length < max) {
    arr.push(tag)
  }
}

function showToast(msg, type = 'error') {
  toast.value = { msg, type }
  setTimeout(() => { toast.value = null }, 3000)
}

onMounted(async () => {
  try {
    const res = await getProfile()
    if (res.code === 0 && res.data) {
      const d = res.data
      if (d.company_name_cn) form.company_name_cn = d.company_name_cn
      if (d.company_name_en) form.company_name_en = d.company_name_en
      if (d.credit_code) form.credit_code = d.credit_code
      if (d.industry) form.industry = d.industry
      if (d.main_products) form.main_products = d.main_products
    }
  } catch {}
})

function handleSave() {
  showToast(t('common.info_saved'), 'success')
  setTimeout(() => router.push('/dashboard'), 500)
}

async function handleSubmit() {
  errors.company_name_cn = form.company_name_cn ? '' : t('info.company_required')
  errors.credit_code = form.credit_code ? '' : t('info.credit_required')
  if (form.credit_code && form.credit_code.length !== 18) {
    errors.credit_code = t('info.credit_18')
  }

  if (Object.values(errors).some(e => e)) return

  loading.value = true
  try {
    const res = await submitProfile({
      name: form.company_name_cn,
      id_card: form.credit_code,
      gender: '',
      income_range: form.industry,
      income_source: form.fund_sources.join(',') || 'Business revenue',
      address: form.funding_country,
      company_name_cn: form.company_name_cn,
      company_name_en: form.company_name_en,
      credit_code: form.credit_code,
      customer_countries: form.customer_countries,
      supplier_countries: form.supplier_countries,
      funding_country: form.funding_country,
      industry: form.industry,
      main_products: form.main_products,
      initial_wealth: form.initial_wealth,
      ongoing_income: form.ongoing_income,
      fund_sources: form.fund_sources,
    })
    if (res.code === 0) {
      showToast(t('common.info_submitted'), 'success')
      setTimeout(() => router.push('/shareholder'), 800)
    } else {
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
.info-page { display: flex; flex-direction: column; min-height: 100vh; background: #f5f5f5; font-family: 'Univers Next for HSBC', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif; }
.progress-bar-wrap { background: #fff; border-bottom: 1px solid #eee; padding: 16px 0; }
.progress-bar-inner { max-width: 900px; margin: 0 auto; padding: 0 32px; }
.progress-text { font-size: 13px; color: #666; margin-bottom: 8px; display: block; }
.progress-track { height: 4px; background: #e5e5e5; border-radius: 2px; overflow: hidden; }
.progress-fill { height: 100%; background: #DB0011; border-radius: 2px; transition: width 0.3s; }
.page-body { flex: 1; padding: 32px 0 120px; }
.page-body-inner { max-width: 900px; margin: 0 auto; padding: 0 32px; }
.page-title { font-size: 32px; font-weight: 300; color: #333; margin-bottom: 12px; }
.page-subtitle { font-size: 14px; color: #666; line-height: 1.6; margin-bottom: 16px; }
.contact-link { font-size: 13px; color: #666; margin-bottom: 12px; }
.contact-link a { color: #0073CF; text-decoration: underline; cursor: pointer; }
.privacy-note { display: flex; align-items: flex-start; gap: 8px; padding: 12px 16px; background: #f0f0f0; border-radius: 4px; margin-bottom: 24px; }
.privacy-note svg { flex-shrink: 0; margin-top: 1px; }
.privacy-note span { font-size: 13px; color: #666; line-height: 1.5; }
.section-block { background: #fff; border-left: 4px solid #DB0011; border-radius: 4px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); margin-bottom: 24px; overflow: hidden; }
.section-heading { font-size: 16px; font-weight: 600; color: #333; padding: 16px 24px; margin: 0; border-bottom: 1px solid #eee; }
.section-body { padding: 24px; }
.section-note { font-size: 13px; color: #666; line-height: 1.6; margin-bottom: 20px; padding: 10px 14px; background: #f8f9fa; border-radius: 4px; }
.field-row { margin-bottom: 20px; }
.field-row:last-child { margin-bottom: 0; }
.field-label { display: block; font-size: 14px; color: #333; margin-bottom: 8px; font-weight: 400; }
.field-label.required::after { content: '*'; color: #DB0011; margin-left: 4px; }
.field-input { width: 100%; height: 44px; padding: 0 14px; border: 1px solid #ccc; border-radius: 4px; font-size: 14px; color: #333; background: #fff; outline: none; transition: border-color 0.2s; box-sizing: border-box; }
.field-input:focus { border-color: #DB0011; }
.field-input.error { border-color: #DB0011; }
.field-textarea { height: auto; padding: 12px 14px; resize: vertical; font-family: inherit; }
.error-text { font-size: 12px; color: #DB0011; margin-top: 4px; }
.tag-selector { display: flex; flex-wrap: wrap; gap: 8px; }
.tag-item { display: inline-flex; align-items: center; padding: 6px 16px; border: 1px solid #ccc; border-radius: 20px; font-size: 13px; color: #666; cursor: pointer; transition: all 0.2s; user-select: none; }
.tag-item:hover { border-color: #DB0011; color: #DB0011; }
.tag-item.active { background: #DB0011; border-color: #DB0011; color: #fff; }
.checkbox-group { display: flex; flex-direction: column; gap: 10px; }
.checkbox-label { display: flex; align-items: center; gap: 10px; font-size: 14px; color: #333; cursor: pointer; }
.checkbox-label input[type="checkbox"] { display: none; }
.checkbox-custom { width: 18px; height: 18px; border: 1.5px solid #ccc; border-radius: 3px; flex-shrink: 0; position: relative; transition: all 0.2s; }
.checkbox-label input:checked + .checkbox-custom { background: #DB0011; border-color: #DB0011; }
.checkbox-label input:checked + .checkbox-custom::after { content: ''; position: absolute; left: 5px; top: 2px; width: 5px; height: 9px; border: solid #fff; border-width: 0 2px 2px 0; transform: rotate(45deg); }
.declaration-block { margin-bottom: 32px; }
.declaration-block p { font-size: 12px; color: #999; line-height: 1.7; }
.bottom-bar { position: fixed; bottom: 0; left: 0; right: 0; background: #fff; border-top: 1px solid #eee; padding: 16px 0; z-index: 100; }
.bottom-bar-inner { max-width: 900px; margin: 0 auto; padding: 0 32px; display: flex; align-items: center; justify-content: space-between; }
.bottom-bar-left { display: flex; gap: 24px; }
.bar-link { font-size: 14px; color: #333; text-decoration: underline; cursor: pointer; }
.bar-link:hover { color: #DB0011; }
.btn-next { min-width: 120px; height: 44px; padding: 0 32px; background: #DB0011; color: #fff; border: none; border-radius: 4px; font-size: 16px; font-weight: 500; cursor: pointer; transition: background 0.2s; }
.btn-next:hover { background: #af000e; }
.btn-next:disabled { background: #e8a0a0; cursor: not-allowed; }
.page-footer { background: #fff; border-top: 1px solid #ddd; padding: 20px 0; }
.footer-inner { max-width: 900px; margin: 0 auto; padding: 0 32px; }
.footer-links { display: flex; flex-wrap: wrap; gap: 20px; margin-bottom: 12px; }
.footer-links a { font-size: 12px; color: #333; cursor: pointer; }
.footer-links a:hover { text-decoration: underline; }
.footer-copyright { font-size: 11px; color: #888; text-align: right; }
.toast { position: fixed; top: 80px; left: 50%; transform: translateX(-50%); padding: 12px 28px; border-radius: 4px; font-size: 14px; z-index: 2000; animation: fadeIn 0.2s; }
.toast.error { background: #fff0f0; color: #DB0011; border: 1px solid #DB0011; }
.toast.success { background: #f0fff4; color: #00847F; border: 1px solid #00847F; }
@keyframes fadeIn { from { opacity: 0; transform: translateX(-50%) translateY(-10px); } to { opacity: 1; transform: translateX(-50%) translateY(0); } }
@media (max-width: 768px) { .page-body-inner, .progress-bar-inner, .bottom-bar-inner, .footer-inner { padding: 0 16px; } .page-title { font-size: 24px; } .tag-selector { gap: 6px; } .tag-item { padding: 4px 12px; font-size: 12px; } }
.loading-spinner { display: inline-block; width: 18px; height: 18px; border: 2px solid rgba(255,255,255,0.3); border-top-color: #fff; border-radius: 50%; animation: spin 0.6s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
