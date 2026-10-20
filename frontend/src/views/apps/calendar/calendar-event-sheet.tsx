'use client'

import Link from 'next/link'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import type { CalendarApiEvent } from '@/lib/calendar/types'
import { formatDueAt, formatDueLabel } from '@/lib/datetime'
import { cn } from '@/lib/utils'

type CalendarEventSheetProps = {
  event: CalendarApiEvent | null
  canChangeFollowUp: boolean
  onOpenChange: (open: boolean) => void
  onCompleteFollowUp: (event: CalendarApiEvent) => void
  onEditFollowUp: (event: CalendarApiEvent) => void
}

const CalendarEventSheet = ({
  event,
  canChangeFollowUp,
  onOpenChange,
  onCompleteFollowUp,
  onEditFollowUp
}: CalendarEventSheetProps) => {
  const pendingFollowUp = event?.type === 'follow_up' && (event.status === 'pending' || event.status === 'overdue')

  return (
    <Sheet open={event !== null} onOpenChange={open => !open && onOpenChange(false)}>
      <SheetContent className='overflow-y-auto sm:max-w-lg'>
        <SheetHeader>
          <SheetTitle>{event?.type_label ?? 'Calendar event'}</SheetTitle>
        </SheetHeader>
        {event && (
          <div className='flex flex-col gap-5 px-4 pb-6'>
            <div className='flex flex-wrap items-center gap-2'>
              <Badge variant='outline' className={cn(event.status === 'overdue' && 'text-destructive')}>
                {event.type_label}
              </Badge>
              {event.status_label && (
                <Badge variant='outline' className={cn(event.status === 'overdue' && 'text-destructive')}>
                  {event.status_label}
                </Badge>
              )}
            </div>
            {event.metadata.follow_up_title && <p className='text-sm font-medium'>{event.metadata.follow_up_title}</p>}
            {event.metadata.description && <p className='text-sm whitespace-pre-wrap'>{event.metadata.description}</p>}
            <dl className='grid gap-3 text-sm sm:grid-cols-2'>
              <div>
                <dt className='text-muted-foreground'>Case</dt>
                <dd className='font-medium'>
                  <Link href={`/opportunities/${event.case.id}`} className='hover:underline'>
                    {event.case.case_number}
                  </Link>
                </dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Customer</dt>
                <dd className='font-medium'>{event.customer.name}</dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Property</dt>
                <dd className='font-medium'>{event.property?.name ?? '—'}</dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Staff</dt>
                <dd className='font-medium'>{event.staff?.display_name || event.staff?.name || 'Unassigned'}</dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Date / time</dt>
                <dd className='font-medium' title={event.start}>
                  {formatDueLabel(event.start, new Date(), event.status)}
                </dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Timestamp</dt>
                <dd className='font-medium'>{formatDueAt(event.start) || '—'}</dd>
              </div>
              {event.metadata.amount_label && (
                <div>
                  <dt className='text-muted-foreground'>Amount</dt>
                  <dd className='font-medium'>{event.metadata.amount_label}</dd>
                </div>
              )}
              {event.case.stage_label && (
                <div>
                  <dt className='text-muted-foreground'>Case stage</dt>
                  <dd className='font-medium'>{event.case.stage_label}</dd>
                </div>
              )}
            </dl>
            <div className='flex flex-wrap gap-2'>
              <Button render={<Link href={`/opportunities/${event.case.id}`} />} nativeButton={false} variant='outline'>
                Open case
              </Button>
              {pendingFollowUp && (
                <Button type='button' disabled={!canChangeFollowUp} onClick={() => onCompleteFollowUp(event)}>
                  Complete
                </Button>
              )}
              {pendingFollowUp && (
                <Button type='button' variant='outline' disabled={!canChangeFollowUp} onClick={() => onEditFollowUp(event)}>
                  Edit
                </Button>
              )}
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}

export default CalendarEventSheet
