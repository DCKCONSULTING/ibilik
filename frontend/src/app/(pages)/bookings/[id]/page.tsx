import type { Metadata } from 'next'

import { RequirePermission } from '@/components/auth/require-permission'
import BookingDetailView from '@/views/crm/bookings/booking-detail'

export const metadata: Metadata = {
  title: 'Booking'
}

const BookingDetailPage = () => {
  return (
    <RequirePermission permission='bookings.view_booking'>
      <BookingDetailView />
    </RequirePermission>
  )
}

export default BookingDetailPage
