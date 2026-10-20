import type { Metadata } from 'next'

import { RequirePermission } from '@/components/auth/require-permission'
import OpportunityDetailView from '@/views/crm/pipeline/opportunity-detail'

export const metadata: Metadata = {
  title: 'Case'
}

const OpportunityDetailPage = () => {
  return (
    <RequirePermission permission={['opportunities.view_opportunity', 'cases.view_case']}>
      <OpportunityDetailView />
    </RequirePermission>
  )
}

export default OpportunityDetailPage
