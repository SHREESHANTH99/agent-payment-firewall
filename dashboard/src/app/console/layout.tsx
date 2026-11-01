import { ConsoleSidebar } from '@/components/ConsoleSidebar'
import { ConsoleHeader } from '@/components/ConsoleHeader'

export default function ConsoleLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-paper">
      <ConsoleSidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <ConsoleHeader />
        <main className="flex-1 overflow-y-auto p-4 md:p-6" id="main-content">
          {children}
        </main>
      </div>
    </div>
  )
}
