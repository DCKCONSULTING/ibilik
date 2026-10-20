import type { ReactNode } from 'react'

import type { Metadata } from 'next'

import { RequirePermission } from '@/components/auth/require-permission'

export const metadata: Metadata = {
  title: 'Calendar'
}

const CalendarLayout = ({ children }: { children: ReactNode }) => {
  return <RequirePermission permission='calendar.view_calendar'>{children}</RequirePermission>
}

export default CalendarLayout
