import type { Metadata } from 'next'

import { RequirePermission } from '@/components/auth/require-permission'
import ModulePlaceholder from '@/views/crm/module-placeholder'

export const metadata: Metadata = {
  title: 'Reports'
}

const ReportsPage = () => {
  return (
    <RequirePermission permission='reports.view_report'>
      <ModulePlaceholder title='Reports' description='Operational and management reports for iBilik CRM.' />
    </RequirePermission>
  )
}

export default ReportsPage
