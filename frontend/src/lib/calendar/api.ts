import { api } from '@/lib/api'
import type { CalendarEventsResponse } from '@/lib/calendar/types'

export const calendarApi = {
  getEvents(query?: Record<string, string | number | boolean | undefined>) {
    return api.get<CalendarEventsResponse>('/api/calendar/events/', { query })
  }
}
