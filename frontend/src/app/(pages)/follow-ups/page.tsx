import { Suspense } from 'react'

import type { Metadata } from 'next'

import { RequirePermission } from '@/components/auth/require-permission'
import FollowUpsPageView from '@/views/crm/follow-ups'

export const metadata: Metadata = {
  title: 'Follow-ups'
}

const FollowUpsPage = () => {
  return (
    <RequirePermission permission={['opportunities.view_opportunity', 'cases.view_case']}>
      <Suspense fallback={<p className='text-muted-foreground text-sm'>Loading follow-ups…</p>}>
        <FollowUpsPageView />
      </Suspense>
    </RequirePermission>
  )
}

export default FollowUpsPage
