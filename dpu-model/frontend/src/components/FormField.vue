<template>
  <div class="form-group">
    <label :class="{ required: isRequired }">{{ label }}</label>
    <select v-if="type === 'select'" class="form-input" :class="{ error: error }" v-model="innerValue" @change="handleChange" @input="handleChange">
      <option value="" disabled>{{ placeholder }}</option>
      <option v-for="opt in options" :key="opt" :value="opt">{{ opt }}</option>
    </select>
    <div v-else-if="type === 'password'" class="password-wrap">
      <input
        class="form-input"
        :class="{ error: error }"
        :type="showPwd ? 'text' : 'password'"
        v-model="innerValue"
        :placeholder="placeholder"
        :maxlength="maxlength"
        @input="handleChange"
      />
      <span class="pwd-toggle" @click="showPwd = !showPwd">{{ showPwd ? 'Hide' : 'Show' }}</span>
    </div>
    <input
      v-else
      class="form-input"
      :class="{ error: error }"
      :type="type"
      v-model="innerValue"
      :placeholder="placeholder"
      :maxlength="maxlength"
      @input="handleChange"
    />
    <div v-if="error" class="error-text">{{ error }}</div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  label: { type: String, default: '' },
  modelValue: { type: [String, Number], default: '' },
  type: { type: String, default: 'text' },
  placeholder: { type: String, default: '' },
  isRequired: { type: Boolean, default: false },
  error: { type: String, default: '' },
  maxlength: { type: [String, Number], default: undefined },
  options: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue'])

const innerValue = ref(props.modelValue)
const showPwd = ref(false)

watch(() => props.modelValue, (v) => { innerValue.value = v })

function handleChange() {
  emit('update:modelValue', innerValue.value)
}
</script>

<style scoped>
.password-wrap {
  position: relative;
}
.pwd-toggle {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 13px;
  color: #666;
  cursor: pointer;
  user-select: none;
  transition: color 0.2s;
}
.pwd-toggle:hover {
  color: #DB0011;
}
</style>
