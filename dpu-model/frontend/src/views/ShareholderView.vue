<template>
  <div class="shareholder-page">
    <!-- 进度条 -->
    <div class="progress-bar-wrap">
      <div class="progress-bar-inner">
        <span class="progress-text">{{ t('shareholder.progress') }}</span>
        <div class="progress-track">
          <div class="progress-fill" style="width: 100%"></div>
        </div>
      </div>
    </div>

    <div class="page-body">
      <div class="page-body-inner">
        <!-- 标题 -->
        <h1 class="page-title">{{ t('shareholder.title') }}</h1>
        <p class="page-subtitle">{{ t('shareholder.subtitle') }}</p>
        <div class="tip-box">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <circle cx="8" cy="8" r="7" stroke="#FF9F0A" stroke-width="1.2"/>
            <line x1="8" y1="5" x2="8" y2="9" stroke="#FF9F0A" stroke-width="1.2" stroke-linecap="round"/>
            <circle cx="8" cy="11.5" r="0.8" fill="#FF9F0A"/>
          </svg>
          <span>{{ t('shareholder.tip') }}</span>
        </div>

        <!-- 人员卡片列表 -->
        <div v-for="(person, idx) in persons" :key="idx" class="person-card">
          <div class="person-header" @click="person.expanded = !person.expanded">
            <div class="person-header-left">
              <span class="person-index">{{ idx + 1 }}.</span>
              <span class="person-role">{{ person.role }}</span>
              <span class="person-dash"> - </span>
              <span class="person-name">{{ person.name_en }} {{ person.name_cn }}</span>
            </div>
            <div class="person-header-right">
              <span class="incomplete-badge" v-if="!isPersonComplete(person)">
                {{ t('shareholder.incomplete') }}
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <circle cx="7" cy="7" r="6" stroke="#FF9F0A" stroke-width="1.2"/>
                  <line x1="7" y1="4" x2="7" y2="8" stroke="#FF9F0A" stroke-width="1.2" stroke-linecap="round"/>
                  <circle cx="7" cy="10" r="0.7" fill="#FF9F0A"/>
                </svg>
              </span>
              <span class="complete-badge" v-else>
                {{ t('shareholder.complete') }}
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <circle cx="7" cy="7" r="6" fill="#00847F"/>
                  <path d="M4 7L6 9L10 5" stroke="#fff" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
              </span>
              <svg :class="['chevron', { rotated: person.expanded }]" width="12" height="8" viewBox="0 0 12 8" fill="none">
                <path d="M1 1.5L6 6.5L11 1.5" stroke="#333" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </div>
          </div>

          <div v-if="person.expanded" class="person-body">
            <!-- 证件类型 -->
            <div class="field-row">
              <label class="field-label">{{ t('shareholder.id_doc_type') }}</label>
              <div class="radio-group">
                <label v-for="opt in idDocTypes" :key="opt" class="radio-label">
                  <input type="radio" :name="'idtype-'+idx" :value="opt" v-model="person.id_doc_type" />
                  <span class="radio-custom"></span>
                  <span>{{ opt }}</span>
                </label>
              </div>
            </div>

            <!-- 证件正面上传 -->
            <div class="field-row">
              <label class="field-label">{{ t('shareholder.id_front') }}</label>
              <div class="upload-area" @click="triggerUpload(idx, 'front')" @dragover.prevent @drop.prevent="handleDrop($event, idx, 'front')">
                <div v-if="!person.id_front" class="upload-placeholder">
                  <svg width="40" height="32" viewBox="0 0 40 32" fill="none">
                    <rect x="1" y="1" width="38" height="30" rx="3" stroke="#ccc" stroke-width="1.5" stroke-dasharray="4 3"/>
                    <path d="M20 10v12M14 16h12" stroke="#ccc" stroke-width="1.5" stroke-linecap="round"/>
                  </svg>
                  <p>{{ t('shareholder.drag_drop') }} <a>{{ t('shareholder.browse') }}</a></p>
                </div>
                <div v-else class="upload-preview">
                  <span>{{ person.id_front.name }}</span>
                  <a class="remove-file" @click.stop="person.id_front = null">✕</a>
                </div>
              </div>
              <input type="file" :ref="el => setUploadRef(idx, 'front', el)" class="hidden-input" accept="image/*" @change="handleFileChange($event, idx, 'front')" />
            </div>

            <!-- 证件背面上传 -->
            <div class="field-row">
              <label class="field-label">{{ t('shareholder.id_back') }}</label>
              <div class="upload-area" @click="triggerUpload(idx, 'back')" @dragover.prevent @drop.prevent="handleDrop($event, idx, 'back')">
                <div v-if="!person.id_back" class="upload-placeholder">
                  <svg width="40" height="32" viewBox="0 0 40 32" fill="none">
                    <rect x="1" y="1" width="38" height="30" rx="3" stroke="#ccc" stroke-width="1.5" stroke-dasharray="4 3"/>
                    <path d="M20 10v12M14 16h12" stroke="#ccc" stroke-width="1.5" stroke-linecap="round"/>
                  </svg>
                  <p>{{ t('shareholder.drag_drop') }} <a>{{ t('shareholder.browse') }}</a></p>
                </div>
                <div v-else class="upload-preview">
                  <span>{{ person.id_back.name }}</span>
                  <a class="remove-file" @click.stop="person.id_back = null">✕</a>
                </div>
              </div>
              <input type="file" :ref="el => setUploadRef(idx, 'back', el)" class="hidden-input" accept="image/*" @change="handleFileChange($event, idx, 'back')" />
              <p class="upload-note">{{ t('shareholder.upload_note') }}</p>
            </div>

            <!-- 出生日期 -->
            <div class="field-row">
              <label class="field-label">{{ t('shareholder.dob') }}</label>
              <input class="field-input" type="date" v-model="person.dob" placeholder="DD/MM/YYYY" />
            </div>

            <!-- 国籍 -->
            <div class="field-row">
              <label class="field-label">{{ t('shareholder.nationality') }}</label>
              <select class="field-input" v-model="person.nationality">
                <option value="" disabled>{{ t('shareholder.select') }}</option>
                <option v-for="c in countryOptions" :key="c" :value="c">{{ c }}</option>
              </select>
            </div>

            <!-- 手机号 -->
            <div class="field-row">
              <label class="field-label">{{ t('shareholder.mobile') }}</label>
              <div class="phone-row">
                <select class="field-input phone-code" v-model="person.phone_code">
                  <option value="+86">+86</option>
                  <option value="+852">+852</option>
                  <option value="+1">+1</option>
                  <option value="+44">+44</option>
                  <option value="+81">+81</option>
                </select>
                <input class="field-input phone-number" v-model="person.phone" :placeholder="t('shareholder.enter_mobile')" />
              </div>
              <p class="field-hint">{{ t('shareholder.sign_hint') }}</p>
            </div>

            <!-- 邮箱 -->
            <div class="field-row">
              <label class="field-label">{{ t('shareholder.email') }}</label>
              <input class="field-input" type="email" v-model="person.email" :placeholder="t('shareholder.enter_email')" />
              <p class="field-hint">{{ t('shareholder.email_hint') }}</p>
            </div>
          </div>
        </div>

        <!-- 新增股东 -->
        <button class="btn-add-shareholder" @click="addPerson">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M8 3v10M3 8h10" stroke="#DB0011" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
          {{ t('shareholder.add') }}
        </button>

        <!-- 声明 -->
        <div class="declaration-block">
          <p>{{ t('shareholder.declaration') }}</p>
        </div>
      </div>
    </div>

    <!-- 底部操作栏 -->
    <div class="bottom-bar">
      <div class="bottom-bar-inner">
        <div class="bottom-bar-left">
          <a class="bar-link" @click="$router.push('/info')">← {{ t('common.back') }}</a>
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
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { submitShareholder } from '../api/index.js'
import { useI18n } from '../utils/i18n.js'

const router = useRouter()
const { t } = useI18n()
const loading = ref(false)
const toast = ref(null)

const idDocTypes = [
  'PRC Resident Identity Card',
  'Mainland Travel Permit for Hong Kong and Macau Residents',
  'Passport',
]
const countryOptions = ['China', 'Hong Kong', 'United States', 'Canada', 'United Kingdom', 'Japan', 'Singapore', 'Australia']

function createPerson(role = 'Shareholder', nameEn = '', nameCn = '') {
  return reactive({
    role,
    name_en: nameEn,
    name_cn: nameCn,
    expanded: false,
    id_doc_type: 'PRC Resident Identity Card',
    id_front: null,
    id_back: null,
    dob: '',
    nationality: 'China',
    phone_code: '+86',
    phone: '',
    email: '',
  })
}

const persons = ref([
  createPerson('Legal representative', 'LAU, Tsz Lan', '刘芷兰'),
  createPerson('Shareholder - Director', 'CHAN, Tai Man', '陈大文'),
  createPerson('Shareholder', 'LEE, Siu Ming', '李小明'),
  createPerson('Director', 'Cheung, Yat Sum', '张一心'),
])
// 默认展开第一个
persons.value[0].expanded = true

function isPersonComplete(person) {
  return person.dob && person.phone && person.email
}

function addPerson() {
  persons.value.push(createPerson('Shareholder', '', ''))
  // 展开新加的
  persons.value[persons.value.length - 1].expanded = true
}

// 文件上传
const uploadRefs = {}
function setUploadRef(idx, side, el) {
  uploadRefs[`${idx}-${side}`] = el
}
function triggerUpload(idx, side) {
  const el = uploadRefs[`${idx}-${side}`]
  if (el) el.click()
}
function handleFileChange(event, idx, side) {
  const file = event.target.files[0]
  if (!file) return
  if (file.size > 10 * 1024 * 1024) {
    showToast(t('shareholder.file_too_large'))
    return
  }
  const person = persons.value[idx]
  if (side === 'front') person.id_front = file
  else person.id_back = file
}
function handleDrop(event, idx, side) {
  const file = event.dataTransfer.files[0]
  if (!file) return
  if (file.size > 10 * 1024 * 1024) {
    showToast(t('shareholder.file_too_large'))
    return
  }
  const person = persons.value[idx]
  if (side === 'front') person.id_front = file
  else person.id_back = file
}

function showToast(msg, type = 'error') {
  toast.value = { msg, type }
  setTimeout(() => { toast.value = null }, 3000)
}

function handleSave() {
  showToast(t('common.info_saved'), 'success')
  setTimeout(() => router.push('/dashboard'), 500)
}

async function handleSubmit() {
  loading.value = true
  try {
    const res = await submitShareholder({
      shareholders: persons.value.map(p => ({
        name: `${p.name_en} ${p.name_cn}`.trim(),
        id_card: p.id_doc_type,
        share_ratio: p.role.includes('Shareholder') ? 25 : 0,
        investment_type: '货币',
        investment_amount: 100000,
        role: p.role,
        dob: p.dob,
        nationality: p.nationality,
        phone: `${p.phone_code}${p.phone}`,
        email: p.email,
      })),
    })
    if (res.code === 0) {
      showToast(t('common.info_submitted'), 'success')
      setTimeout(() => router.push('/quota'), 800)
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
.shareholder-page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: #f5f5f5;
  font-family: 'Univers Next for HSBC', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

/* 进度条 */
.progress-bar-wrap {
  background: #fff;
  border-bottom: 1px solid #eee;
  padding: 16px 0;
}
.progress-bar-inner {
  max-width: 900px;
  margin: 0 auto;
  padding: 0 32px;
}
.progress-text {
  font-size: 13px;
  color: #666;
  margin-bottom: 8px;
  display: block;
}
.progress-track {
  height: 4px;
  background: #e5e5e5;
  border-radius: 2px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: #DB0011;
  border-radius: 2px;
}

/* 主体 */
.page-body {
  flex: 1;
  padding: 32px 0 120px;
}
.page-body-inner {
  max-width: 900px;
  margin: 0 auto;
  padding: 0 32px;
}
.page-title {
  font-size: 32px;
  font-weight: 300;
  color: #333;
  margin-bottom: 12px;
}
.page-subtitle {
  font-size: 14px;
  color: #666;
  line-height: 1.6;
  margin-bottom: 16px;
}
.tip-box {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #fff8e6;
  border: 1px solid #ffe4a0;
  border-radius: 4px;
  margin-bottom: 24px;
}
.tip-box svg { flex-shrink: 0; }
.tip-box span {
  font-size: 13px;
  color: #666;
}

/* 人员卡片 */
.person-card {
  background: #fff;
  border-radius: 4px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  margin-bottom: 16px;
  overflow: hidden;
}
.person-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  cursor: pointer;
  transition: background 0.2s;
}
.person-header:hover {
  background: #fafafa;
}
.person-header-left {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  color: #333;
  font-weight: 500;
  flex-wrap: wrap;
}
.person-index {
  font-weight: 600;
}
.person-role {
  color: #666;
}
.person-dash {
  color: #999;
}
.person-name {
  font-weight: 600;
  color: #333;
}
.person-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}
.incomplete-badge {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #FF9F0A;
  font-weight: 500;
}
.complete-badge {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #00847F;
  font-weight: 500;
}
.chevron {
  transition: transform 0.2s;
}
.chevron.rotated {
  transform: rotate(180deg);
}

/* 人员详情 */
.person-body {
  padding: 24px;
  border-top: 1px solid #eee;
}
.field-row {
  margin-bottom: 20px;
}
.field-row:last-child {
  margin-bottom: 0;
}
.field-label {
  display: block;
  font-size: 14px;
  color: #333;
  margin-bottom: 8px;
  font-weight: 400;
}
.field-input {
  width: 100%;
  height: 44px;
  padding: 0 14px;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 14px;
  color: #333;
  background: #fff;
  outline: none;
  box-sizing: border-box;
  transition: border-color 0.2s;
}
.field-input:focus {
  border-color: #DB0011;
}
.field-hint {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}

/* 单选组 */
.radio-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.radio-label {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  color: #333;
  cursor: pointer;
}
.radio-label input[type="radio"] {
  display: none;
}
.radio-custom {
  width: 18px;
  height: 18px;
  border: 1.5px solid #ccc;
  border-radius: 50%;
  flex-shrink: 0;
  position: relative;
  transition: all 0.2s;
}
.radio-label input:checked + .radio-custom {
  border-color: #DB0011;
}
.radio-label input:checked + .radio-custom::after {
  content: '';
  position: absolute;
  top: 3px;
  left: 3px;
  width: 9px;
  height: 9px;
  background: #DB0011;
  border-radius: 50%;
}

/* 上传区域 */
.upload-area {
  border: 1.5px dashed #ccc;
  border-radius: 4px;
  padding: 24px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.2s;
}
.upload-area:hover {
  border-color: #DB0011;
}
.upload-placeholder p {
  font-size: 13px;
  color: #999;
  margin-top: 8px;
}
.upload-placeholder a {
  color: #0073CF;
  text-decoration: underline;
  cursor: pointer;
}
.upload-preview {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  font-size: 13px;
  color: #333;
}
.remove-file {
  color: #DB0011;
  cursor: pointer;
  font-size: 16px;
}
.upload-note {
  font-size: 12px;
  color: #999;
  margin-top: 8px;
}
.hidden-input {
  display: none;
}

/* 手机号行 */
.phone-row {
  display: flex;
  gap: 8px;
}
.phone-code {
  width: 100px;
  flex-shrink: 0;
}
.phone-number {
  flex: 1;
}

/* 新增股东按钮 */
.btn-add-shareholder {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  height: 48px;
  background: #fff;
  border: 1.5px dashed #ccc;
  border-radius: 4px;
  font-size: 14px;
  color: #DB0011;
  cursor: pointer;
  transition: all 0.2s;
  margin-bottom: 24px;
}
.btn-add-shareholder:hover {
  border-color: #DB0011;
  background: #fef0f0;
}

/* 声明 */
.declaration-block {
  margin-bottom: 32px;
}
.declaration-block p {
  font-size: 12px;
  color: #999;
  line-height: 1.7;
}

/* 底部操作栏 */
.bottom-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: #fff;
  border-top: 1px solid #eee;
  padding: 16px 0;
  z-index: 100;
}
.bottom-bar-inner {
  max-width: 900px;
  margin: 0 auto;
  padding: 0 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.bottom-bar-left {
  display: flex;
  gap: 24px;
}
.bar-link {
  font-size: 14px;
  color: #333;
  text-decoration: underline;
  cursor: pointer;
}
.bar-link:hover {
  color: #DB0011;
}
.btn-next {
  min-width: 120px;
  height: 44px;
  padding: 0 32px;
  background: #DB0011;
  color: #fff;
  border: none;
  border-radius: 4px;
  font-size: 16px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
}
.btn-next:hover {
  background: #af000e;
}
.btn-next:disabled {
  background: #e8a0a0;
  cursor: not-allowed;
}

/* 页脚 */
.page-footer {
  background: #fff;
  border-top: 1px solid #ddd;
  padding: 20px 0;
}
.footer-inner {
  max-width: 900px;
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
.footer-links a:hover {
  text-decoration: underline;
}
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

/* Loading */
.loading-spinner {
  display: inline-block;
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 移动端 */
@media (max-width: 768px) {
  .page-body-inner,
  .progress-bar-inner,
  .bottom-bar-inner,
  .footer-inner {
    padding: 0 16px;
  }
  .page-title {
    font-size: 24px;
  }
  .person-header {
    padding: 12px 16px;
  }
  .person-body {
    padding: 16px;
  }
  .phone-row {
    flex-direction: column;
  }
  .phone-code {
    width: 100%;
  }
}
</style>
