import {
  LayoutDashboard,
  CheckSquare,
  ListOrdered,
  Scale,
  Link2,
  Shield,
  Compass,
  LogOut,
  ArrowLeft,
  type LucideIcon,
} from 'lucide-react'

export interface NavItemConfig {
  href: string
  label: string
  icon: LucideIcon
  exact?: boolean
  badgeKey?: 'escalations' | 'frozen'
}

export const MAIN_BOTTOM_NAV_ITEMS: NavItemConfig[] = [
  { href: '/console', label: 'Overview', icon: LayoutDashboard, exact: true },
  { href: '/console/approvals', label: 'Approvals', icon: CheckSquare, badgeKey: 'escalations' },
  { href: '/console/intents', label: 'Intents', icon: ListOrdered },
  { href: '/console/mandates', label: 'Mandates', icon: Scale, badgeKey: 'frozen' },
]

export const MORE_SHEET_ITEMS: NavItemConfig[] = [
  { href: '/console/audit', label: 'Audit chain', icon: Link2 },
  { href: '/console/controls', label: 'Risk controls', icon: Shield },
  { href: '/playground', label: 'Try the Playground', icon: Compass },
]

export const FULL_TELEMETRY_ITEMS: NavItemConfig[] = [
  { href: '/console', label: 'Overview', icon: LayoutDashboard, exact: true },
  { href: '/console/approvals', label: 'Approvals', icon: CheckSquare, badgeKey: 'escalations' },
  { href: '/console/intents', label: 'Intents', icon: ListOrdered },
]

export const FULL_GOVERNANCE_ITEMS: NavItemConfig[] = [
  { href: '/console/mandates', label: 'Mandates', icon: Scale, badgeKey: 'frozen' },
  { href: '/console/audit', label: 'Audit chain', icon: Link2 },
  { href: '/console/controls', label: 'Risk controls', icon: Shield },
]
