'use client'

import type { ReactNode } from 'react'

import { RequirePermission } from '@/components/auth/require-permission'

const MailLayout = ({ children }: { children: ReactNode }) => {
  return <RequirePermission permission='inbox.view_inbox'>{children}</RequirePermission>
}

export default MailLayout
