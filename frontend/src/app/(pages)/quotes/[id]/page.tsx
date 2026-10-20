import type { Metadata } from 'next'

import { RequirePermission } from '@/components/auth/require-permission'
import QuoteDetailView from '@/views/crm/quotes/quote-detail'

export const metadata: Metadata = {
  title: 'Quotation'
}

const QuoteDetailPage = () => {
  return (
    <RequirePermission permission='quotes.view_quote'>
      <QuoteDetailView />
    </RequirePermission>
  )
}

export default QuoteDetailPage
