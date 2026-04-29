import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useLangStore = defineStore('lang', () => {
  const lang = ref(localStorage.getItem('dpu_lang') || 'en')

  const isZh = computed(() => lang.value === 'zh')
  const isEn = computed(() => lang.value === 'en')

  function setLang(l) {
    lang.value = l
    localStorage.setItem('dpu_lang', l)
  }

  function toggle() {
    setLang(lang.value === 'en' ? 'zh' : 'en')
  }

  return { lang, isZh, isEn, setLang, toggle }
})
