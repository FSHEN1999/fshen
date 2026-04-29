'use client'

import { useRef, useState } from 'react'

/**
 * 6位验证码方格输入组件 + Get code按钮
 */
export default function OtpInput({ value, onChange, onSendCode, countdown, disabled }) {
  const inputRefs = useRef([])
  const digits = value.padEnd(6, ' ').split('').slice(0, 6)

  function handleInput(idx, e) {
    const char = e.target.value.replace(/\D/g, '').slice(-1)
    const newDigits = [...digits.map(d => d.trim())]
    newDigits[idx] = char

    const newValue = newDigits.join('')
    onChange(newValue)

    // 自动跳转下一个
    if (char && idx < 5) {
      inputRefs.current[idx + 1]?.focus()
    }
  }

  function handleKeyDown(idx, e) {
    if (e.key === 'Backspace' && !digits[idx].trim() && idx > 0) {
      inputRefs.current[idx - 1]?.focus()
    }
  }

  function handlePaste(e) {
    e.preventDefault()
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6)
    onChange(pasted)
    const focusIdx = Math.min(pasted.length, 5)
    inputRefs.current[focusIdx]?.focus()
  }

  return (
    <div>
      <label className="block text-[14px] text-hsbc-dark mb-2 font-hsbc">
        Verification code
      </label>
      <div className="flex items-center gap-3">
        {/* 6个方格 */}
        <div className="flex gap-2">
          {[0, 1, 2, 3, 4, 5].map((idx) => (
            <input
              key={idx}
              ref={el => { inputRefs.current[idx] = el }}
              type="text"
              inputMode="numeric"
              maxLength={1}
              value={digits[idx].trim()}
              onChange={e => handleInput(idx, e)}
              onKeyDown={e => handleKeyDown(idx, e)}
              onPaste={idx === 0 ? handlePaste : undefined}
              className={`
                w-[44px] h-[44px] border rounded text-center
                text-[18px] font-medium text-hsbc-dark font-hsbc
                outline-none transition-colors duration-200
                ${digits[idx].trim() ? 'border-hsbc-dark' : 'border-hsbc-border'}
                focus:border-hsbc-dark
              `}
            />
          ))}
        </div>

        {/* Get code 按钮 */}
        <button
          onClick={onSendCode}
          disabled={disabled || countdown > 0}
          className={`
            h-[44px] px-5 text-[14px] font-hsbc whitespace-nowrap
            border rounded transition-colors duration-200
            ${countdown > 0 || disabled
              ? 'border-hsbc-border text-hsbc-light-gray cursor-not-allowed bg-white'
              : 'border-hsbc-border text-hsbc-dark cursor-pointer bg-white hover:border-hsbc-dark hover:text-hsbc-dark'
            }
          `}
        >
          {countdown > 0 ? `${countdown}s` : 'Get code'}
        </button>
      </div>
    </div>
  )
}
