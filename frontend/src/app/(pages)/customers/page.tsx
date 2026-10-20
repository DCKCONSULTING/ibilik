import type { Metadata } from 'next'

import { RequirePermission } from '@/components/auth/require-permission'
import CustomersPageView from '@/views/crm/customers'

export const metadata: Metadata = {
  title: 'Customers'
}

const CustomersPage = () => {
  return (
    <RequirePermission permission='customers.view_customer'>
      <CustomersPageView />
    </RequirePermission>
  )
}

export default CustomersPage
