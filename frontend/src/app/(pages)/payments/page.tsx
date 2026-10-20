import type { Metadata } from 'next'

import { RequirePermission } from '@/components/auth/require-permission'
import PaymentsPageView from '@/views/crm/payments'

export const metadata: Metadata = {
  title: 'Payments'
}

const PaymentsPage = () => {
  return (
    <RequirePermission permission='payments.view_payment'>
      <PaymentsPageView />
    </RequirePermission>
  )
}

export default PaymentsPage
