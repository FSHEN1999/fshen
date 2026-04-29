import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('dpu_token') || '')
  const phone = ref(localStorage.getItem('dpu_phone') || '')

  const isLoggedIn = computed(() => !!token.value)

  function setLogin(newToken, newPhone) {
    token.value = newToken
    phone.value = newPhone
    localStorage.setItem('dpu_token', newToken)
    localStorage.setItem('dpu_phone', newPhone)
  }

  function logout() {
    token.value = ''
    phone.value = ''
    localStorage.removeItem('dpu_token')
    localStorage.removeItem('dpu_phone')
  }

  return { token, phone, isLoggedIn, setLogin, logout }
})
