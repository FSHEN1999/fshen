/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        'hsbc-red': '#DB0011',
        'hsbc-red-hover': '#AF000E',
        'hsbc-dark': '#333333',
        'hsbc-gray': '#666666',
        'hsbc-light-gray': '#999999',
        'hsbc-border': '#CCCCCC',
        'hsbc-bg': '#F6F6F6',
      },
      fontFamily: {
        hsbc: ['"Univers Next for HSBC"', 'system-ui', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', '"PingFang SC"', '"Microsoft YaHei"', 'sans-serif'],
      },
      fontSize: {
        'hsbc-hero': ['36px', { lineHeight: '44px', fontWeight: '300', letterSpacing: '-0.3px' }],
        'hsbc-subtitle': ['14px', { lineHeight: '20px', fontWeight: '400' }],
        'hsbc-label': ['14px', { lineHeight: '20px', fontWeight: '400' }],
        'hsbc-body': ['14px', { lineHeight: '20px', fontWeight: '400' }],
        'hsbc-small': ['12px', { lineHeight: '16px', fontWeight: '400' }],
        'hsbc-footer': ['11px', { lineHeight: '16px', fontWeight: '400' }],
      },
    },
  },
  plugins: [],
}
