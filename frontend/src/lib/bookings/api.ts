import { api } from '@/lib/api'
import type { Booking, BookingListResponse } from '@/lib/bookings/types'

export const bookingsApi = {
  list(query?: Record<string, string | number | boolean | undefined>) {
    return api.get<BookingListResponse>('/api/bookings/', { query })
  },
  get(id: number) {
    return api.get<Booking>(`/api/bookings/${id}/`)
  }
}
