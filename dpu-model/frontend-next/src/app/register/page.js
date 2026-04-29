'use client'

import { useState, useCallback, useEffect } from 'react'
import PhoneInput from '@/components/ui/PhoneInput'
import OtpInput from '@/components/ui/OtpInput'
import Button from '@/components/ui/Button'

export default function RegisterPage() {
  const [phone, setPhone] = useState('')
  const [phoneError, setPhoneError] = useState('')
  const [otp, setOtp] = useState('')
  const [countdown, setCountdown] = useState(0)
  const [loading, setLoading] = useState(false)
  const [toast, setToast] = useState(null)

  // 倒计时逻辑
  useEffect(() => {
    if (countdown <= 0) return
    const timer = setTimeout(() => setCountdown(c => c - 1), 1000)
    return () => clearTimeout(timer)
  }, [countdown])

  // 手机号验证
  const validatePhone = useCallback((val) => {
    if (!val) return '请输入手机号'
    if (!/^1[3-9]\d{9}$/.test(val)) return '手机号格式不正确'
    return ''
  }, [])

  // 发送验证码
  const handleSendCode = useCallback(async () => {
    const err = validatePhone(phone)
    if (err) {
      setPhoneError(err)
      return
    }
    setPhoneError('')

    try {
      const res = await fetch('/api/auth/sms-code', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone }),
      })
      const data = await res.json()
      if (data.code === 0) {
        setCountdown(60)
        showToast('验证码已发送', 'success')
      } else {
        showToast(data.message, 'error')
      }
    } catch {
      showToast('网络连接失败，请检查网络', 'error')
    }
  }, [phone, validatePhone])

  // 提交注册
  const handleNext = useCallback(async () => {
    const err = validatePhone(phone)
    if (err) {
      setPhoneError(err)
      return
    }
    if (otp.length !== 6) {
      showToast('请输入6位验证码', 'error')
      return
    }
    setPhoneError('')
    setLoading(true)

    try {
      // 模拟注册/登录请求
      showToast('注册成功', 'success')
    } catch {
      showToast('网络连接失败', 'error')
    } finally {
      setLoading(false)
    }
  }, [phone, otp, validatePhone])

  function showToast(msg, type) {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  return (
    <div className="flex flex-col min-h-screen bg-white font-hsbc">
      {/* ===== 顶部导航栏 ===== */}
      <header className="flex items-center h-[56px] px-8 border-b border-[#EEEEEE] bg-white shrink-0">
        <div className="flex items-center gap-2.5">
          {/* HSBC Logo */}
          <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
            <rect width="32" height="32" rx="2" fill="#DB0011"/>
            <path d="M8 10H14V14H8V10Z" fill="white"/>
            <path d="M18 10H24V14H18V10Z" fill="white"/>
            <path d="M13 13H19V19H13V13Z" fill="white"/>
            <path d="M8 18H14V22H8V18Z" fill="white"/>
            <path d="M18 18H24V22H18V18Z" fill="white"/>
          </svg>
          <span className="text-[16px] font-semibold text-hsbc-dark tracking-[0.3px]">
            HSBC Express Finance
          </span>
          {/* 右箭头 */}
          <svg width="8" height="14" viewBox="0 0 8 14" fill="none" className="ml-0.5">
            <path d="M1 1L7 7L1 13" stroke="#333" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
      </header>

      {/* ===== 主体内容 ===== */}
      <main className="flex flex-1 min-h-0">
        {/* 左侧表单区 */}
        <div className="flex-1 max-w-[620px] px-8 lg:px-14 pt-12 pb-10 flex flex-col">
          {/* 副标题 */}
          <p className="text-hsbc-subtitle text-hsbc-gray mb-2">
            HSBC Express Finance
          </p>

          {/* 主标题 */}
          <h1 className="text-[36px] leading-[44px] font-light text-hsbc-dark tracking-[-0.3px] mb-10">
            Create account to start your<br className="hidden sm:block" /> application
          </h1>

          {/* 手机号输入 */}
          <div className="mb-7">
            <PhoneInput
              value={phone}
              onChange={(val) => { setPhone(val); setPhoneError('') }}
              error={phoneError}
            />
          </div>

          {/* 验证码输入 */}
          <div className="mb-7">
            <OtpInput
              value={otp}
              onChange={setOtp}
              onSendCode={handleSendCode}
              countdown={countdown}
              disabled={!phone}
            />
          </div>

          {/* 已有账号链接 */}
          <div className="text-[14px] text-hsbc-dark mb-10">
            Already have an account?{' '}
            <a className="text-hsbc-dark underline cursor-pointer hover:text-hsbc-red transition-colors">
              Log in
            </a>
            <span className="text-hsbc-dark ml-0.5">&rsaquo;</span>
          </div>

          {/* 底部操作按钮 - 推到底部 */}
          <div className="flex items-center justify-between mt-auto pt-6">
            <a className="flex items-center gap-1 text-[14px] text-hsbc-dark cursor-pointer hover:text-hsbc-red transition-colors">
              <span className="text-[18px] leading-none">&lsaquo;</span>
              <span>Back</span>
            </a>

            <Button
              onClick={handleNext}
              loading={loading}
              disabled={!phone || otp.length < 6}
            >
              Next
            </Button>
          </div>
        </div>

        {/* 右侧香港夜景图 */}
        <div className="hidden lg:block flex-1 min-w-0 relative">
          <img
            src="https://picsum.photos/1200/800"
            alt="Hong Kong skyline at night"
            className="absolute inset-0 w-full h-full object-cover"
          />
          {/* Chat with us 浮窗 */}
          <div className="absolute bottom-6 right-6 flex flex-col items-center gap-1.5 bg-[#00B6B0] rounded-lg px-4 py-3 cursor-pointer shadow-lg hover:shadow-xl transition-shadow">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
              <rect x="3" y="4" width="18" height="14" rx="2" stroke="white" strokeWidth="1.5"/>
              <path d="M8 10H16M8 14H12" stroke="white" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
            <span className="text-white text-[11px] font-medium whitespace-nowrap">Chat with us</span>
          </div>
        </div>
      </main>

      {/* ===== 底部页脚 ===== */}
      <footer className="border-t border-[#EEEEEE] px-8 py-5 bg-white shrink-0">
        {/* 链接行 */}
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 mb-3">
          <a className="text-[12px] text-hsbc-dark cursor-pointer hover:underline">Platform Terms</a>
          <a className="text-[12px] text-hsbc-dark cursor-pointer hover:underline">Privacy Notice</a>
          <a className="text-[12px] text-hsbc-dark cursor-pointer hover:underline">Hyperlink Policy</a>
          <span className="flex items-center gap-1 text-[12px] text-hsbc-dark cursor-pointer hover:underline">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <circle cx="7" cy="7" r="5.5" stroke="#333" strokeWidth="1"/>
              <ellipse cx="7" cy="7" rx="3" ry="5.5" stroke="#333" strokeWidth="0.8"/>
              <line x1="1.5" y1="5" x2="12.5" y2="5" stroke="#333" strokeWidth="0.7"/>
              <line x1="1.5" y1="9" x2="12.5" y2="9" stroke="#333" strokeWidth="0.7"/>
            </svg>
            English
          </span>
        </div>

        {/* 说明文字 */}
        <p className="text-[11px] leading-[16px] text-hsbc-light-gray mb-2">
          This website/application is HSBC Express Finance – a technology platform that connects sellers and lenders.
          HSBC Express Finance Data Services Limited, a non-banking subsidiary of HSBC, operates HSBC Express Finance
          and provides services related to the technology platform. HSBC Express Finance is not a lender.
        </p>

        {/* 版权信息 */}
        <p className="text-[11px] leading-[16px] text-hsbc-light-gray text-right">
          &copy; Copyright. HSBC Express Finance Data Services Limited 2025. All rights reserved.
        </p>
      </footer>

      {/* Toast提示 */}
      {toast && (
        <div className={`
          fixed top-[70px] left-1/2 -translate-x-1/2 px-6 py-2.5 rounded text-[13px] z-[9999]
          animate-[fadeIn_0.3s_ease]
          ${toast.type === 'success' ? 'bg-[#F6FFED] text-[#52C41A] border border-[#B7EB8F]' : ''}
          ${toast.type === 'error' ? 'bg-[#FFF2F0] text-hsbc-red border border-[#FFCCC7]' : ''}
        `}>
          {toast.msg}
        </div>
      )}
    </div>
  )
}
