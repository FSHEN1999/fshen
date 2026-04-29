<template>
  <header class="hsbc-nav">
    <div class="hsbc-nav-inner">
      <div class="hsbc-nav-logo" @click="$router.push('/info')">
        <svg width="40" height="28" viewBox="0 0 40 28" fill="none">
          <rect x="0.5" y="0.5" width="39" height="27" rx="3" stroke="#ccc" fill="white"/>
          <polygon points="8,6 20,14 8,22" fill="#DB0011"/>
          <polygon points="32,6 20,14 32,22" fill="#DB0011"/>
          <polygon points="8,6 32,6 20,14" fill="white"/>
          <polygon points="8,22 32,22 20,14" fill="white"/>
          <polygon points="8,6 20,6 20,14" fill="#DB0011"/>
          <polygon points="32,22 20,22 20,14" fill="#DB0011"/>
        </svg>
        <span class="nav-brand">HSBC Express Finance</span>
      </div>
      <div class="hsbc-nav-right">
        <span class="nav-phone">{{ authStore.phone }}</span>
        <a class="nav-logout" @click="handleLogout">{{ t('header.logout') }}</a>
      </div>
    </div>
  </header>
</template>

<script setup>
import { useAuthStore } from '../stores/auth.js'
import { useUserStore } from '../stores/user.js'
import { useRouter } from 'vue-router'
import { useI18n } from '../utils/i18n.js'

const { t } = useI18n()
const authStore = useAuthStore()
const userStore = useUserStore()
const router = useRouter()

function handleLogout() {
  authStore.logout()
  userStore.reset()
  router.push('/login')
}
</script>

<style scoped>
.hsbc-nav {
  height: 56px;
  border-bottom: 1px solid #eee;
  background: #fff;
}
.hsbc-nav-inner {
  max-width: 1200px;
  margin: 0 auto;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 32px;
}
.hsbc-nav-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}
.nav-brand {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  letter-spacing: 0.3px;
}
.hsbc-nav-right {
  display: flex;
  align-items: center;
  gap: 16px;
}
.nav-phone {
  font-size: 13px;
  color: #666;
}
.nav-logout {
  font-size: 13px;
  color: #333;
  cursor: pointer;
  text-decoration: underline;
  transition: color 0.2s;
}
.nav-logout:hover {
  color: #DB0011;
}
@media (max-width: 768px) {
  .hsbc-nav-inner { padding: 0 16px; }
  .nav-brand { font-size: 14px; }
}
</style>
