import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/LoginView.vue'),
    meta: { guest: true },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('../views/RegisterView.vue'),
    meta: { guest: true },
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('../views/DashboardView.vue'),
    meta: { auth: true, noDashHeader: true },
  },
  {
    path: '/info',
    name: 'InfoForm',
    component: () => import('../views/InfoFormView.vue'),
    meta: { auth: true },
  },
  {
    path: '/shareholder',
    name: 'Shareholder',
    component: () => import('../views/ShareholderView.vue'),
    meta: { auth: true },
  },
  {
    path: '/quota',
    name: 'Quota',
    component: () => import('../views/QuotaView.vue'),
    meta: { auth: true },
  },
  {
    path: '/approval',
    name: 'Approval',
    component: () => import('../views/ApprovalView.vue'),
    meta: { auth: true },
  },
  {
    path: '/',
    redirect: '/login',
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/login',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  if (to.meta.auth && !authStore.isLoggedIn) {
    next('/login')
  } else if (to.meta.guest && authStore.isLoggedIn) {
    next('/dashboard')
  } else {
    next()
  }
})

export default router
