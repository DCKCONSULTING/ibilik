'use client'

import type { ReactNode } from 'react'

import { RequirePermission } from '@/components/auth/require-permission'

const DashboardLayout = ({ children }: { children: ReactNode }) => {
  return <RequirePermission permission='dashboard.view_dashboard'>{children}</RequirePermission>
}

export default DashboardLayout
