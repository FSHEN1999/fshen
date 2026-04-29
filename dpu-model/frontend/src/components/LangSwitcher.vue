<template>
  <div v-if="show" class="lang-overlay" @click="show = false">
    <div class="lang-popup" @click.stop>
      <h3 class="lang-title">选择语言 / Select Language</h3>
      <div class="lang-options">
        <label class="lang-option" :class="{ active: langStore.isEn }" @click="selectLang('en')">
          <span class="lang-radio" :class="{ checked: langStore.isEn }"></span>
          <span>English</span>
        </label>
        <label class="lang-option" :class="{ active: langStore.isZh }" @click="selectLang('zh')">
          <span class="lang-radio" :class="{ checked: langStore.isZh }"></span>
          <span>中文</span>
        </label>
      </div>
      <button class="lang-close" @click="show = false">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <path d="M1 1L13 13M13 1L1 13" stroke="#333" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useLangStore } from '../stores/lang.js'

const langStore = useLangStore()
const show = ref(false)

function selectLang(l) {
  langStore.setLang(l)
  show.value = false
}

function open() {
  show.value = true
}

defineExpose({ open })
</script>

<style scoped>
.lang-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  animation: fadeIn 0.15s;
}
.lang-popup {
  background: #fff;
  border-radius: 8px;
  padding: 28px 32px;
  min-width: 280px;
  position: relative;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
}
.lang-title {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  margin-bottom: 20px;
  text-align: center;
}
.lang-options {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.lang-option {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border: 1px solid #eee;
  border-radius: 6px;
  cursor: pointer;
  font-size: 15px;
  color: #333;
  transition: all 0.2s;
}
.lang-option:hover {
  border-color: #DB0011;
  background: #fef0f0;
}
.lang-option.active {
  border-color: #DB0011;
  background: #fef0f0;
}
.lang-radio {
  width: 18px;
  height: 18px;
  border: 2px solid #ccc;
  border-radius: 50%;
  flex-shrink: 0;
  position: relative;
  transition: all 0.2s;
}
.lang-radio.checked {
  border-color: #DB0011;
}
.lang-radio.checked::after {
  content: '';
  position: absolute;
  top: 3px;
  left: 3px;
  width: 8px;
  height: 8px;
  background: #DB0011;
  border-radius: 50%;
}
.lang-close {
  position: absolute;
  top: 12px;
  right: 12px;
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  line-height: 1;
}
.lang-close:hover svg path {
  stroke: #DB0011;
}
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
</style>
