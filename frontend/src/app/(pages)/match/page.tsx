import { Suspense } from 'react'

import type { Metadata } from 'next'

import { RequirePermission } from '@/components/auth/require-permission'
import MatchPageView from '@/views/crm/match'

export const metadata: Metadata = {
  title: 'Match'
}

const MatchPage = () => {
  return (
    <RequirePermission permission='match.view_match'>
      <Suspense fallback={<p className='text-muted-foreground text-sm'>Loading Match…</p>}>
        <MatchPageView />
      </Suspense>
    </RequirePermission>
  )
}

export default MatchPage
