'use client'

import Link from 'next/link'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { formatDueAt, formatDueLabel, formatRelativeTime } from '@/lib/datetime'
import type { CaseFollowUp } from '@/lib/pipeline/types'
import { cn } from '@/lib/utils'

type FollowUpDetailSheetProps = {
  followUp: CaseFollowUp | null
  canChange: boolean
  onOpenChange: (open: boolean) => void
  onComplete: (followUp: CaseFollowUp) => void
  onEdit: (followUp: CaseFollowUp) => void
  onCancel: (followUp: CaseFollowUp) => void
  onCustomer: (followUp: CaseFollowUp) => void
}

const FollowUpDetailSheet = ({
  followUp,
  canChange,
  onOpenChange,
  onComplete,
  onEdit,
  onCancel,
  onCustomer
}: FollowUpDetailSheetProps) => {
  const pending = followUp?.status === 'pending' || followUp?.status === 'overdue'

  return (
    <Sheet open={followUp !== null} onOpenChange={open => !open && onOpenChange(false)}>
      <SheetContent className='overflow-y-auto sm:max-w-lg'>
        <SheetHeader>
          <SheetTitle>{followUp?.title ?? 'Follow-up'}</SheetTitle>
        </SheetHeader>
        {followUp && (
          <div className='flex flex-col gap-5 px-4 pb-6'>
            <div className='flex flex-wrap items-center gap-2'>
              <Badge variant='outline' className={cn(followUp.status === 'overdue' && 'text-destructive')}>
                {followUp.status_label}
              </Badge>
              <Badge variant='outline'>{followUp.type_label}</Badge>
            </div>
            {followUp.description && <p className='text-sm whitespace-pre-wrap'>{followUp.description}</p>}
            <dl className='grid gap-3 text-sm sm:grid-cols-2'>
              <div>
                <dt className='text-muted-foreground'>Case</dt>
                <dd className='font-medium'>
                  {followUp.case ? (
                    <Link href={`/opportunities/${followUp.case.id}`} className='hover:underline'>
                      {followUp.case.case_number}
                    </Link>
                  ) : (
                    '—'
                  )}
                </dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Customer</dt>
                <dd className='font-medium'>
                  {followUp.customer ? (
                    <button type='button' className='hover:underline' onClick={() => onCustomer(followUp)}>
                      {followUp.customer.name}
                    </button>
                  ) : (
                    '—'
                  )}
                </dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Property</dt>
                <dd className='font-medium'>{followUp.property?.name ?? '—'}</dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Assigned staff</dt>
                <dd className='font-medium'>
                  {followUp.assigned_to?.display_name || followUp.assigned_to?.name || 'Unassigned'}
                </dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Due</dt>
                <dd className={cn('font-medium', followUp.status === 'overdue' && 'text-destructive')} title={followUp.due_at ?? undefined}>
                  {formatDueLabel(followUp.due_at, new Date(), followUp.status)}
                </dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Due timestamp</dt>
                <dd className='font-medium'>{formatDueAt(followUp.due_at) || '—'}</dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Created by</dt>
                <dd className='font-medium'>
                  {followUp.created_by?.display_name || followUp.created_by?.name || '—'}
                </dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Created</dt>
                <dd className='font-medium'>{formatRelativeTime(followUp.created_at) || '—'}</dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Completed</dt>
                <dd className='font-medium'>{formatDueAt(followUp.completed_at) || '—'}</dd>
              </div>
            </dl>
            {followUp.case && (
              <Button render={<Link href={`/opportunities/${followUp.case.id}`} />} nativeButton={false} variant='outline'>
                Open case
              </Button>
            )}
            <div className='flex flex-wrap gap-2'>
              {pending && (
                <Button type='button' disabled={!canChange} onClick={() => onComplete(followUp)}>
                  Complete
                </Button>
              )}
              {pending && (
                <Button type='button' variant='outline' disabled={!canChange} onClick={() => onEdit(followUp)}>
                  Edit
                </Button>
              )}
              {pending && (
                <Button type='button' variant='ghost' disabled={!canChange} onClick={() => onCancel(followUp)}>
                  Cancel
                </Button>
              )}
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}

export default FollowUpDetailSheet
