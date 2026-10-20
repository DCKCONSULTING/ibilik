import type { Metadata } from 'next'

import { RequirePermission } from '@/components/auth/require-permission'
import QuotesPageView from '@/views/crm/quotes'

export const metadata: Metadata = {
  title: 'Quotations'
}

const QuotesPage = () => {
  return (
    <RequirePermission permission='quotes.view_quote'>
      <QuotesPageView />
    </RequirePermission>
  )
}

export default QuotesPage
