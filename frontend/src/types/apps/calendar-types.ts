import type { CalendarApiEvent, CalendarEventType } from '@/lib/calendar/types'

export type CalendarView = 'month' | 'week' | 'day'

export interface CalendarEvent {
  id: string
  title: string
  description?: string
  start: Date
  end: Date
  allDay?: boolean
  color?: events
  location?: string
  source?: CalendarApiEvent
}

export type events = 'family' | 'business' | 'personal' | 'holiday' | 'etc' | CalendarEventType

/** @deprecated Use `events` — kept for existing imports */
export type EventColor = events
