import { IBM_Plex_Sans, IBM_Plex_Mono, Instrument_Serif } from 'next/font/google'
import { RealtimeProvider } from '@/hooks/useRealtime'
import './globals.css'

const ibmSans = IBM_Plex_Sans({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-ibm-sans',
  display: 'swap',
})

const ibmMono = IBM_Plex_Mono({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  variable: '--font-ibm-mono',
  display: 'swap',
})

const instrumentSerif = Instrument_Serif({
  subsets: ['latin'],
  weight: ['400'],
  variable: '--font-serif',
  display: 'swap',
})

export const metadata = {
  title: 'Agent Payment Firewall — Settlement Interception for Autonomous AI',
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
    <html lang="en" className={`${ibmSans.variable} ${ibmMono.variable} ${instrumentSerif.variable}`}>
      <body className="min-h-screen bg-background text-foreground antialiased flex flex-col font-sans">
        <RealtimeProvider>
          {children}
        </RealtimeProvider>
      </body>
    </html>
  )
}
