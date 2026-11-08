import { describe, it, expect } from 'vitest'
import { BRAND } from '@/lib/brand'
import { metadata } from '@/app/layout'
import fs from 'fs'
import path from 'path'

describe('Brand Identity Verification', () => {
  it('defines valid Spendlatch brand constants', () => {
    expect(BRAND.name).toBe('Spendlatch')
    expect(BRAND.tagline).toBe('Payment firewall for AI agents')
    expect(BRAND.repoUrl).toContain('github.com')
  })

  it('root layout page title contains brand name', () => {
    expect(metadata.title).toContain(BRAND.name)
    expect(metadata.title).toContain(BRAND.tagline)
  })

  it('no legacy brand name "Gatekeeper" appears in dashboard source files', () => {
    const srcDir = path.resolve(__dirname, '..')
    const violations: string[] = []

    function scanDir(dir: string) {
      const entries = fs.readdirSync(dir, { withFileTypes: true })
      for (const entry of entries) {
        const fullPath = path.join(dir, entry.name)
        if (entry.isDirectory()) {
          if (entry.name !== 'node_modules' && entry.name !== '.next') {
            scanDir(fullPath)
          }
        } else if (/\.(tsx|ts|js|jsx|json|md)$/.test(entry.name)) {
          // Exclude this test file itself from self-flagging
          if (entry.name === 'brand.test.ts') continue
          const content = fs.readFileSync(fullPath, 'utf-8')
          if (/gatekeeper/i.test(content)) {
            violations.push(fullPath)
          }
        }
      }
    }

    scanDir(srcDir)
    expect(violations).toEqual([])
  })
})
