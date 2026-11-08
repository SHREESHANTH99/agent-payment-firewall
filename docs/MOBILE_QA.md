# Mobile QA Verification Runbook (5-Minute Test)

This runbook covers manual and automated verification of the responsive mobile and tablet experience across the whole dashboard application.

---

## 1. Automated Verification Commands

Run dashboard unit tests:
```bash
cd dashboard && npm test
```

Run dashboard production build:
```bash
cd dashboard && npm run build
```

---

## 2. Manual Checklist: Phone Viewport (< 768px, e.g. iPhone 14 / 390px)

### A. Landing Page (`/`)
- [ ] **Header**: Only logo, color theme toggle, and hamburger menu button are visible. No cramped or wrapping nav links.
- [ ] **Mobile Sheet**: Tapping menu opens full-screen sheet with section links and CTAs:
  - "Try the Playground"
  - "View sample console"
  - "Sign in with token"
  - "View on GitHub"
- [ ] **Hero Section**:
  - Main headline breaks cleanly on word boundaries.
  - Subtitle copy reads *"policy-driven payment firewall"*.
  - Hero CTAs stack full width in exact order: [Try the Playground] -> [View sample console] -> [GitHub].
  - Meta chips wrap neatly without jagged spacing.
- [ ] **Horizontal Overflow**: No page-level horizontal scroll (`window.scrollX === 0`). Wide elements (tables, code blocks, animated ledger) scroll within their own container.

---

### B. Operator Console (`/console?demo=1`)
- [ ] **Header**: Compact header displaying only the page title and the `Sample mode` chip. Offline indicator is hidden.
- [ ] **Bottom Tab Bar**:
  - Fixed 5-tab bar at bottom: `Overview`, `Approvals` (with badge if pending), `Intents`, `Mandates`, and `More`.
  - Active tab is highlighted with 2px accent bar.
  - Safe-area bottom padding respected so content is not obscured.
- [ ] **"More" Bottom Sheet**:
  - Tapping "More" opens accessible sheet with: `Audit chain`, `Risk controls`, `Try the Playground`, `Exit sample mode`, `Back to site`, and `Theme toggle`.
  - Closing sheet works via `X` button, tapping backdrop, or pressing `Escape`.
- [ ] **KPI Grid**: 2-column layout; the 5th card ("Frozen mandates") spans full width (`col-span-2`) with no orphan spacing.
- [ ] **List Views (Intents & Audit)**: Replaced table with native mobile card list. Tapping "Filter" opens a clean bottom filter sheet. Long hashes are truncated and have a 1-tap copy button.

---

### C. Judge Playground (`/playground`)
- [ ] **Header & Tabs**: Setup, Attack, and Firewall tabs are docked right below the header.
- [ ] **Attack Tab & Sticky Action Bar**:
  - Sticky bottom action bar displays prominent "Send intent" button.
  - Tapping "Send intent" shows a spinner and automatically switches the active tab to "Firewall / Result" when evaluation completes.

---

### D. Login Screen (`/console/login`)
- [ ] Card is vertically and horizontally centered with `100dvh` support.
- [ ] Input font size is at least 16px to prevent iOS auto-zoom on focus.
- [ ] All touch targets meet minimum 44px by 44px standard.

---

## 3. Tablet Viewport (768px – 1023px, e.g. iPad Mini / 768px)
- [ ] **Sidebar Rail**: Renders an icon-only side rail (`w-16`).
- [ ] **Expand on Tap**: Tapping the expand button widens the rail to `w-56` with labels; tapping outside collapses it back.
- [ ] **Bottom Bar**: Phone bottom bar is hidden on tablet.
