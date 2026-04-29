'use client'

import { useState } from 'react'

/**
 * 手机号输入组件（含+86国际区号选择器）
 */
export default function PhoneInput({ value, onChange, error }) {
  const [focused, setFocused] = useState(false)

  function handleChange(e) {
    // 只允许数字，最多11位
    const val = e.target.value.replace(/\D/g, '').slice(0, 11)
    onChange(val)
  }

  return (
    <div>
      <label className="block text-[14px] text-hsbc-dark mb-2 font-hsbc">
        Mobile number
      </label>
      <div className="flex">
        {/* 区号选择 */}
        <div className={`
          flex items-center gap-1.5 px-3 h-[44px] border border-r-0 rounded-l
          bg-white text-[14px] text-hsbc-dark cursor-pointer min-w-[80px]
          ${focused ? 'border-hsbc-dark' : 'border-hsbc-border'}
          ${error ? 'border-hsbc-red' : ''}
        `}>
          <span>+86</span>
          <svg width="12" height="7" viewBox="0 0 12 7" fill="none" className="ml-0.5">
            <path d="M1 1L6 6L11 1" stroke="#333" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>

        {/* 手机号输入 */}
        <input
          type="tel"
          value={value}
          onChange={handleChange}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          className={`
            flex-1 h-[44px] px-3 border rounded-r outline-none
            text-[14px] text-hsbc-dark font-hsbc
            transition-colors duration-200
            ${focused ? 'border-hsbc-dark' : 'border-hsbc-border'}
            ${error ? 'border-hsbc-red' : ''}
          `}
        />
      </div>

      {error && (
        <p className="text-hsbc-red text-[12px] mt-1 font-hsbc">{error}</p>
      )}
    </div>
  )
}
