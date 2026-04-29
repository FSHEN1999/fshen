'use client'

/**
 * HSBC风格按钮组件
 * variant: 'primary'(红色填充) | 'text'(文字按钮)
 */
export default function Button({
  children,
  variant = 'primary',
  disabled = false,
  loading = false,
  className = '',
  onClick,
  ...props
}) {
  const baseClasses = 'inline-flex items-center justify-center transition-all duration-200 font-hsbc'

  const variants = {
    primary: `h-[40px] px-7 rounded bg-hsbc-red text-white text-[14px] font-medium
      hover:bg-hsbc-red-hover active:bg-hsbc-red-hover
      disabled:bg-[#E8A0A0] disabled:cursor-not-allowed`,
    text: `text-[14px] text-hsbc-dark hover:text-hsbc-red cursor-pointer bg-transparent border-none p-0`,
  }

  return (
    <button
      className={`${baseClasses} ${variants[variant]} ${className}`}
      disabled={disabled || loading}
      onClick={onClick}
      {...props}
    >
      {loading ? (
        <span className="inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
      ) : (
        children
      )}
    </button>
  )
}
