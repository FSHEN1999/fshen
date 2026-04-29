<template>
  <div class="sms-input-group">
    <input
      class="form-input sms-input"
      :class="{ error: errorMsg }"
      v-model="code"
      type="text"
      maxlength="6"
      placeholder="请输入6位验证码"
      @input="$emit('update:modelValue', code)"
    />
    <button
      class="sms-btn"
      :disabled="countdown > 0 || sending"
      @click="handleSend"
    >
      {{ countdown > 0 ? `${countdown}s` : (sending ? '发送中...' : 'Get code') }}
    </button>
  </div>
  <div v-if="errorMsg" class="error-text">{{ errorMsg }}</div>
</template>

<script setup>
import { ref, watch, onUnmounted } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  phone: { type: String, default: '' },
  sendFn: { type: Function, required: true },
})
const emit = defineEmits(['update:modelValue'])

const code = ref(props.modelValue)
const countdown = ref(0)
const sending = ref(false)
const errorMsg = ref('')

watch(() => props.modelValue, (v) => { code.value = v })

let timer = null

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

async function handleSend() {
  if (!props.phone) {
    errorMsg.value = '请先输入手机号'
    return
  }
  sending.value = true
  errorMsg.value = ''
  try {
    const res = await props.sendFn(props.phone)
    if (res.code === 0) {
      countdown.value = 60
      timer = setInterval(() => {
        countdown.value--
        if (countdown.value <= 0) clearInterval(timer)
      }, 1000)
    } else {
      errorMsg.value = res.message
    }
  } catch (e) {
    errorMsg.value = '网络连接失败，请检查网络'
  } finally {
    sending.value = false
  }
}
</script>

<style scoped>
.sms-input-group {
  display: flex;
  gap: 12px;
}
.sms-input {
  flex: 1;
}
.sms-btn {
  min-width: 110px;
  height: 44px;
  background: #fff;
  color: #333;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 14px;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s;
}
.sms-btn:hover:not(:disabled) {
  border-color: #333;
  color: #DB0011;
}
.sms-btn:disabled {
  color: #bbb;
  border-color: #e0e0e0;
  cursor: not-allowed;
}
</style>
