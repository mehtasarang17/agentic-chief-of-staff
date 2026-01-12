import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Chief of Staff AI | Your Executive AI Assistant',
  description: 'Industry-grade AI-powered executive assistant with multi-agent orchestration',
  icons: {
    icon: '/favicon.ico',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-gradient-mesh">
        <div className="fixed inset-0 bg-gradient-glow pointer-events-none" />
        <div className="relative z-10">
          {children}
        </div>
      </body>
    </html>
  )
}
