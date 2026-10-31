import { ConsoleSidebar } from '@/components/ConsoleSidebar'

export default function ConsoleLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-paper">
      <ConsoleSidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="h-10 border-b border-border bg-paper-low flex items-center px-4 justify-between shrink-0">
          <span className="font-mono text-2xs text-ink-muted uppercase tracking-widest hidden sm:block">
            Agent Payment Firewall — Operator Console
          </span>
          <div className="flex items-center gap-2 ml-auto">
            <a
              href="/console?demo=1"
              className="font-mono text-2xs text-ink-muted hover:text-ink uppercase tracking-wide transition-colors"
            >
              Demo mode
            </a>
            <span className="text-border">|</span>
            <a
              href="/"
              className="font-mono text-2xs text-ink-muted hover:text-ink uppercase tracking-wide transition-colors"
            >
              Landing
            </a>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-4 md:p-6" id="main-content">
          {children}
        </main>
      </div>
    </div>
  )
}
