import './globals.css'

export const metadata = {
  title: 'HSBC Express Finance - Create Account',
  description: 'Create account to start your application',
}

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
