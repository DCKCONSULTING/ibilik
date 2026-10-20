import { Suspense } from 'react'

import { EventCalendar } from '@/views/apps/calendar'

const CalendarApp = () => {
  return (
    <Suspense fallback={<p className='text-muted-foreground text-sm'>Loading calendar…</p>}>
      <EventCalendar />
    </Suspense>
  )
}

export default CalendarApp
