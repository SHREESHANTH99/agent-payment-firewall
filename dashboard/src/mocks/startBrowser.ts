export async function startDemoMocks(): Promise<void> {
  if (typeof window === 'undefined') return

  const { worker } = await import('./browser')
  await worker.start({
    onUnhandledRequest: 'bypass',
    serviceWorker: { url: '/mockServiceWorker.js' },
  })
}
