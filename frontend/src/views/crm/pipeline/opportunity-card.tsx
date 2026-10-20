'use client'

import { useRef } from 'react'

import { useRouter } from 'next/navigation'

import { useNow } from '@/hooks/use-now'
import { formatDueAt, formatRelativeTime } from '@/lib/datetime'
import type { Opportunity } from '@/lib/pipeline/types'
import { staffName } from '@/lib/pipeline/validation'
import { cn } from '@/lib/utils'

type OpportunityCardProps = {
  opportunity: Opportunity
  disabled?: boolean
}

const OpportunityCard = ({ opportunity, disabled = false }: OpportunityCardProps) => {
  const router = useRouter()
  const now = useNow()
  const dragged = useRef(false)
  const activity = formatRelativeTime(opportunity.updated_at, now)
  const assigned = staffName(opportunity)
  const nextFollowUp = opportunity.next_follow_up
  const overdue = nextFollowUp?.status === 'overdue'

  const openDetail = () => {
    if (dragged.current) {
      dragged.current = false

      return
    }

    router.push(`/opportunities/${opportunity.id}`)
  }

  return (
    <article
      role='link'
      tabIndex={0}
      draggable={!disabled}
      onClick={openDetail}
      onKeyDown={event => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          openDetail()
        }
      }}
      onDragStart={event => {
        dragged.current = true
        event.dataTransfer.setData('text/plain', String(opportunity.id))
        event.dataTransfer.effectAllowed = 'move'
      }}
      className={cn(
        'bg-card ring-foreground/10 w-full cursor-pointer rounded-lg p-3 text-left shadow-xs ring-1',
        overdue && 'ring-destructive/40',
        !disabled && 'active:cursor-grabbing'
      )}
    >
      <p className='text-muted-foreground text-xs font-medium tracking-wide'>{opportunity.case_number}</p>
      <p className='text-foreground mt-0.5 truncate text-sm font-semibold'>{opportunity.customer.name}</p>
      <p className='text-foreground mt-0.5 line-clamp-2 text-sm'>{opportunity.title}</p>
      {opportunity.property && (
        <p className='text-muted-foreground mt-1 truncate text-xs'>Property: {opportunity.property.name}</p>
      )}
      <p className='text-muted-foreground mt-1 truncate text-xs'>Staff: {assigned ?? 'Unassigned'}</p>
      <p className={cn('mt-2 truncate text-xs', overdue ? 'text-destructive font-medium' : 'text-muted-foreground')}>
        {nextFollowUp
          ? `Next follow-up: ${formatDueAt(nextFollowUp.due_at, now) || nextFollowUp.title}${overdue ? ' · Overdue' : ''}`
          : 'No pending follow-up'}
      </p>
      {activity && (
        <time className='text-muted-foreground mt-1 block text-xs'>Last activity: {activity}</time>
      )}
    </article>
  )
}

export default OpportunityCard
