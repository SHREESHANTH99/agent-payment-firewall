import { AppHeader } from '@/components/AppHeader'
import { RealtimeProvider } from '@/hooks/useRealtime'
import './globals.css'

export const metadata = {
  title: 'Agent Payment Firewall - Operator Console',
  description: 'Real-time security governance for autonomous AI financial transactions',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-background text-foreground antialiased flex flex-col">
        <RealtimeProvider>
          <AppHeader />
          <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
            {children}
          </main>
        </RealtimeProvider>
      </body>
    </html>
  )
}
