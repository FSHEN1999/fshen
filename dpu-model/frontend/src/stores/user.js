import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUserStore = defineStore('user', () => {
  const profile = ref(null)
  const quota = ref(null)
  const approval = ref(null)

  function setProfile(data) { profile.value = data }
  function setQuota(data) { quota.value = data }
  function setApproval(data) { approval.value = data }
  function reset() {
    profile.value = null
    quota.value = null
    approval.value = null
  }

  return { profile, quota, approval, setProfile, setQuota, setApproval, reset }
})
