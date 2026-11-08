import { RealtimeProvider } from '@/hooks/useRealtime'
import { BRAND } from '@/lib/brand'
import './globals.css'

export const metadata = {
  title: `${BRAND.name} — ${BRAND.tagline}`,
  description: 'Deterministic policy firewall, canary scanning, LLM risk judge, and SHA-256 hash-chained audit ledger for autonomous agent payments.',
  icons: {
    icon: '/favicon.svg',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <head>
        <link
          rel="preconnect"
          href="https://fonts.googleapis.com"
        />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&family=Instrument+Serif&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-screen bg-background text-foreground antialiased flex flex-col font-sans">
        <RealtimeProvider>
          {children}
        </RealtimeProvider>
      </body>
    </html>
  )
}
