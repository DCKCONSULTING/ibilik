import type { Metadata } from 'next'

import { RequirePermission } from '@/components/auth/require-permission'
import PipelinePageView from '@/views/crm/pipeline'

export const metadata: Metadata = {
  title: 'CRM Pipeline'
}

const OpportunitiesPage = () => {
  return (
    <RequirePermission permission={['opportunities.view_opportunity', 'cases.view_case']}>
      <PipelinePageView />
    </RequirePermission>
  )
}

export default OpportunitiesPage
