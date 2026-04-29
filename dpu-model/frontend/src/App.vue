<template>
  <div id="app-root">
    <AppHeader v-if="authStore.isLoggedIn && !isLoginPage && !isFullPage" />
    <router-view />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from './stores/auth.js'
import AppHeader from './components/AppHeader.vue'

const authStore = useAuthStore()
const route = useRoute()

const isLoginPage = computed(() =>
  route.path === '/login' || route.path === '/register'
)
const isFullPage = computed(() =>
  route.path === '/dashboard' || route.path === '/info' || route.path === '/shareholder' || route.path === '/approval'
)
</script>

<style>
/* 全局样式 - HSBC Express Finance 设计规范 */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

:root {
  --hsbc-red: #DB0011;
  --hsbc-red-hover: #af000e;
  --hsbc-red-light: #fef0f0;
  --hsbc-dark: #333333;
  --hsbc-text: #333333;
  --hsbc-text-secondary: #666666;
  --hsbc-text-muted: #999999;
  --hsbc-border: #cccccc;
  --hsbc-border-light: #eeeeee;
  --hsbc-bg: #ffffff;
  --hsbc-bg-section: #f8f9fa;
  --hsbc-green: #00847F;
  --hsbc-blue: #0073CF;
  --hsbc-success: #00847F;
  --hsbc-error: #DB0011;
  --hsbc-warning: #FF9F0A;
  --hsbc-radius: 4px;
  --hsbc-radius-lg: 8px;
  --hsbc-font: 'Univers Next for HSBC', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

body {
  font-family: var(--hsbc-font);
  font-size: 14px;
  color: var(--hsbc-text);
  background: #fff;
  -webkit-font-smoothing: antialiased;
}

#app-root {
  width: 100%;
  min-height: 100vh;
  background: #fff;
  position: relative;
}

/* 通用主按钮 - HSBC红色 */
.btn-primary {
  width: 100%;
  height: 44px;
  background: var(--hsbc-red);
  color: #fff;
  border: none;
  border-radius: var(--hsbc-radius);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s, box-shadow 0.2s;
}
.btn-primary:hover {
  background: var(--hsbc-red-hover);
  box-shadow: 0 2px 8px rgba(219, 0, 17, 0.3);
}
.btn-primary:disabled {
  background: #e8a0a0;
  cursor: not-allowed;
  box-shadow: none;
}

/* 次要按钮 */
.btn-secondary {
  width: 100%;
  height: 44px;
  background: #fff;
  color: var(--hsbc-text);
  border: 1px solid var(--hsbc-border);
  border-radius: var(--hsbc-radius);
  font-size: 14px;
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s;
}
.btn-secondary:hover {
  border-color: var(--hsbc-text);
  color: var(--hsbc-red);
}

/* 通用输入框 */
.form-input {
  width: 100%;
  height: 44px;
  border: 1px solid var(--hsbc-border);
  border-radius: var(--hsbc-radius);
  padding: 0 12px;
  font-size: 14px;
  color: var(--hsbc-text);
  outline: none;
  background: #fff;
  transition: border-color 0.2s;
}
.form-input:focus {
  border-color: var(--hsbc-text);
}
.form-input.error {
  border-color: var(--hsbc-error);
}

/* 错误提示 */
.error-text {
  color: var(--hsbc-error);
  font-size: 12px;
  margin-top: 4px;
}

/* 页面容器 - 内页通用 */
.page-container {
  max-width: 800px;
  margin: 0 auto;
  padding: 32px 40px;
}

/* 必填星号 */
.required::before {
  content: '*';
  color: var(--hsbc-error);
  margin-right: 4px;
}

/* 表单分组 */
.form-group {
  margin-bottom: 20px;
}
.form-group label {
  display: block;
  font-size: 14px;
  color: var(--hsbc-text);
  margin-bottom: 8px;
  font-weight: 400;
}

/* 加载动画 */
.loading-spinner {
  display: inline-block;
  width: 18px;
  height: 18px;
  border: 2px solid #fff;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 提示消息 */
.toast {
  position: fixed;
  top: 70px;
  left: 50%;
  transform: translateX(-50%);
  padding: 10px 24px;
  border-radius: var(--hsbc-radius);
  font-size: 13px;
  z-index: 9999;
  animation: fadeIn 0.3s;
}
.toast.success {
  background: #f6ffed;
  color: var(--hsbc-success);
  border: 1px solid #b7eb8f;
}
.toast.error {
  background: var(--hsbc-red-light);
  color: var(--hsbc-error);
  border: 1px solid #ffccc7;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateX(-50%) translateY(-8px); }
  to { opacity: 1; transform: translateX(-50%) translateY(0); }
}

/* 移动端适配 */
@media (max-width: 768px) {
  .page-container {
    padding: 20px 16px;
  }
}
</style>
