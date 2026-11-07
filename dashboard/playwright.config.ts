import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  use: { baseURL: 'http://127.0.0.1:3100', ...devices['Desktop Chrome'] },
  webServer: { command: 'npm run dev -- --hostname 127.0.0.1 --port 3100', port: 3100, reuseExistingServer: true },
})
