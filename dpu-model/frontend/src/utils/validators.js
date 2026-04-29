/**
 * 前端表单校验规则
 */

// 手机号校验（11位国内手机号）
export function validatePhone(phone) {
  if (!phone) return '请输入手机号'
  if (!/^1[3-9]\d{9}$/.test(phone)) return '手机号格式不正确'
  return ''
}

// 验证码校验（6位数字）
export function validateSmsCode(code) {
  if (!code) return '请输入验证码'
  if (!/^\d{6}$/.test(code)) return '验证码为6位数字'
  return ''
}

// 密码校验（8-16位，包含字母+数字）
export function validatePassword(password) {
  if (!password) return '请输入密码'
  if (password.length < 8 || password.length > 16) return '密码长度8-16位'
  if (!/[a-zA-Z]/.test(password)) return '密码必须包含字母'
  if (!/\d/.test(password)) return '密码必须包含数字'
  return ''
}

// 身份证号校验
export function validateIdCard(idCard) {
  if (!idCard) return '请输入身份证号'
  if (!/^\d{17}[\dXx]$/.test(idCard)) return '身份证号格式不正确'
  // 校验位验证
  const weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
  const checkCodes = '10X98765432'
  let total = 0
  for (let i = 0; i < 17; i++) {
    total += parseInt(idCard[i]) * weights[i]
  }
  if (idCard[17].toUpperCase() !== checkCodes[total % 11]) {
    return '身份证号校验位不正确'
  }
  return ''
}

// 邮箱校验
export function validateEmail(email) {
  if (!email) return '' // 可选字段
  if (!/^[\w.+-]+@[\w-]+\.[\w.]+$/.test(email)) return '邮箱格式不正确'
  return ''
}

// 持股比例校验
export function validateShareRatio(ratio) {
  if (ratio === '' || ratio === null || ratio === undefined) return '请输入持股比例'
  const num = parseFloat(ratio)
  if (isNaN(num) || num <= 0 || num > 100) return '持股比例应在0-100之间'
  return ''
}
