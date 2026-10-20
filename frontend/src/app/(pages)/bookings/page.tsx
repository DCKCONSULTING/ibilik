import type { Metadata } from 'next'

import { RequirePermission } from '@/components/auth/require-permission'
import BookingsPageView from '@/views/crm/bookings'

export const metadata: Metadata = {
  title: 'Bookings'
}

const BookingsPage = () => {
  return (
    <RequirePermission permission='bookings.view_booking'>
      <BookingsPageView />
    </RequirePermission>
  )
}

export default BookingsPage
