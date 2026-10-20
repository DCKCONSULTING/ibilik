import type { Metadata } from 'next'

import { RequirePermission } from '@/components/auth/require-permission'
import AvailabilityPageView from '@/views/crm/availability'

export const metadata: Metadata = {
  title: 'Availability'
}

const AvailabilityPage = () => {
  return (
    <RequirePermission permission='availability.view_availability'>
      <AvailabilityPageView />
    </RequirePermission>
  )
}

export default AvailabilityPage
