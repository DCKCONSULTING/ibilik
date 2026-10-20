'use client'

import { useEffect, useState } from 'react'

import Link from 'next/link'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Field, FieldLabel } from '@/components/ui/field'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Textarea } from '@/components/ui/textarea'
import { formatDueAt, formatRelativeTime } from '@/lib/datetime'
import { assignmentBadgeLabel, canShowAssign, canShowAutoAssign, canShowReassign, relatedRecordHref, staffLabel } from '@/lib/match/display'
import type { MatchRequest, MatchStaff } from '@/lib/match/types'
import { cn } from '@/lib/utils'

type MatchDetailSheetProps = {
  request: MatchRequest | null
  statuses: { id: string; label: string }[]
  priorities: { id: string; label: string }[]
  canAssign: boolean
  canReassign: boolean
  canUnassign: boolean
  canChangeStatus: boolean
  canChangePriority: boolean
  canAddNotes: boolean
  canResolve: boolean
  assigning: boolean
  onOpenChange: (open: boolean) => void
  onCustomer: (request: MatchRequest) => void
  onAssign: (request: MatchRequest, staffId: number) => void
  onReassign: (request: MatchRequest, staffId: number) => void
  onUnassign: (request: MatchRequest) => void
  onAutoAssign: (request: MatchRequest) => void
  onStatus: (request: MatchRequest, status: string) => void
  onPriority: (request: MatchRequest, priority: string) => void
  onNote: (request: MatchRequest, note: string) => void
}

const staffOptionLabel = (user: MatchStaff) => {
  const name = staffLabel(user)
  const role = user.role_name ? ` · ${user.role_name}` : ''
  const properties = user.assigned_properties?.map(item => item.name).filter(Boolean).join(', ')

  return properties ? `${name}${role} · ${properties}` : `${name}${role}`
}

const MatchDetailSheet = ({
  request,
  statuses,
  priorities,
  canAssign,
  canReassign,
  canUnassign,
  canChangeStatus,
  canChangePriority,
  canAddNotes,
  canResolve,
  assigning,
  onOpenChange,
  onCustomer,
  onAssign,
  onReassign,
  onUnassign,
  onAutoAssign,
  onStatus,
  onPriority,
  onNote
}: MatchDetailSheetProps) => {
  const [staffId, setStaffId] = useState<string>('')
  const [note, setNote] = useState('')

  useEffect(() => {
    setStaffId(request?.assigned_to ? String(request.assigned_to.id) : '')
    setNote('')
  }, [request?.id, request?.assigned_to])

  const relatedHref = request ? relatedRecordHref(request) : null
  const staffOptions = request?.assignable_staff ?? []
  const assigned = request?.assigned_to ?? null
  const showAssign = canShowAssign(assigned, canAssign)
  const showReassign = canShowReassign(assigned, canReassign)
  const showAutoAssign = canShowAutoAssign(canAssign)
  const assignmentLabel = assignmentBadgeLabel(request?.assignment_method)

  return (
    <Sheet open={request !== null} onOpenChange={open => !open && onOpenChange(false)}>
      <SheetContent className='overflow-y-auto sm:max-w-xl'>
        <SheetHeader>
          <SheetTitle>{request?.subject ?? 'Request'}</SheetTitle>
        </SheetHeader>
        {request && (
          <div className='flex flex-col gap-5 px-4 pb-6'>
            <div className='flex flex-wrap items-center gap-2'>
              <Badge variant='outline'>{request.request_number}</Badge>
              <Badge variant='outline'>{request.request_type_label}</Badge>
              <Badge
                variant='outline'
                className={cn(
                  request.priority === 'urgent' && 'border-destructive/40 text-destructive',
                  request.priority === 'high' && 'text-amber-700 dark:text-amber-400'
                )}
              >
                {request.priority_label}
              </Badge>
              <Badge variant='outline' className={cn(request.is_overdue && 'text-destructive')}>
                {request.status_label}
              </Badge>
              {assignmentLabel ? <Badge variant='outline'>{assignmentLabel}</Badge> : null}
            </div>
            {request.description && <p className='text-sm whitespace-pre-wrap'>{request.description}</p>}
            <dl className='grid gap-3 text-sm sm:grid-cols-2'>
              <div>
                <dt className='text-muted-foreground'>Customer</dt>
                <dd className='font-medium'>
                  {request.customer ? (
                    <button type='button' className='hover:underline' onClick={() => onCustomer(request)}>
                      {request.customer.name}
                    </button>
                  ) : (
                    '—'
                  )}
                </dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Property</dt>
                <dd className='font-medium'>{request.property?.name ?? '—'}</dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Location</dt>
                <dd className='font-medium'>{request.location?.name ?? '—'}</dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Related record</dt>
                <dd className='font-medium'>
                  {request.related_record ? (
                    relatedHref ? (
                      <Link href={relatedHref} className='hover:underline'>
                        {request.related_record.label}
                        {request.related_record.title ? ` · ${request.related_record.title}` : ''}
                      </Link>
                    ) : (
                      request.related_record.label
                    )
                  ) : (
                    '—'
                  )}
                </dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Assigned to</dt>
                <dd className='font-medium'>
                  {staffLabel(assigned)}
                  {assigned?.role_name ? <span className='text-muted-foreground'> · {assigned.role_name}</span> : null}
                </dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Assignment type</dt>
                <dd className='font-medium'>{request.assignment_method_label || assignmentLabel || '—'}</dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Assigned at</dt>
                <dd className='font-medium'>{formatDueAt(request.assigned_at) || '—'}</dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Workload at assignment</dt>
                <dd className='font-medium'>
                  {request.workload_at_assignment == null
                    ? '—'
                    : `${request.workload_at_assignment} active request${request.workload_at_assignment === 1 ? '' : 's'}`}
                </dd>
              </div>
              {request.assigned_to_workload != null && (
                <div>
                  <dt className='text-muted-foreground'>Current workload</dt>
                  <dd className='font-medium'>
                    {request.assigned_to_workload} active request{request.assigned_to_workload === 1 ? '' : 's'}
                  </dd>
                </div>
              )}
              {request.unassigned_reason && !assigned && (
                <div className='sm:col-span-2'>
                  <dt className='text-muted-foreground'>Unassigned reason</dt>
                  <dd className='font-medium'>{request.unassigned_reason}</dd>
                </div>
              )}
              <div>
                <dt className='text-muted-foreground'>Assigned by</dt>
                <dd className='font-medium'>{staffLabel(request.assigned_by) === 'Unassigned' ? '—' : staffLabel(request.assigned_by)}</dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Created</dt>
                <dd className='font-medium'>{formatRelativeTime(request.created_at) || '—'}</dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Due</dt>
                <dd className={cn('font-medium', request.is_overdue && 'text-destructive')}>
                  {formatDueAt(request.due_at) || '—'}
                </dd>
              </div>
            </dl>

            {request.customer && (
              <div className='rounded-md border p-3 text-sm'>
                <p className='font-medium'>Customer</p>
                <p>{request.customer.name}</p>
                <p className='text-muted-foreground'>{request.customer.email || 'No email'}</p>
                <p className='text-muted-foreground'>{request.customer.phone || 'No phone'}</p>
              </div>
            )}

            <div className='grid gap-3 sm:grid-cols-2'>
              <Field>
                <FieldLabel>Status</FieldLabel>
                <Select
                  value={request.status}
                  disabled={!canChangeStatus && !(canResolve && request.status !== 'resolved')}
                  onValueChange={value => value && onStatus(request, value)}
                >
                  <SelectTrigger className='w-full'>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {statuses.map(item => (
                      <SelectItem key={item.id} value={item.id} disabled={item.id === 'resolved' && !canResolve && !canChangeStatus}>
                        {item.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
              <Field>
                <FieldLabel>Priority</FieldLabel>
                <Select value={request.priority} disabled={!canChangePriority} onValueChange={value => value && onPriority(request, value)}>
                  <SelectTrigger className='w-full'>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {priorities.map(item => (
                      <SelectItem key={item.id} value={item.id}>
                        {item.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
            </div>

            <Field>
              <FieldLabel>Assign to staff</FieldLabel>
              <Select value={staffId || undefined} onValueChange={value => value && setStaffId(value)}>
                <SelectTrigger className='w-full'>
                  <SelectValue placeholder='Select staff' />
                </SelectTrigger>
                <SelectContent>
                  {staffOptions.map(user => (
                    <SelectItem key={user.id} value={String(user.id)}>
                      {staffOptionLabel(user)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <div className='flex flex-wrap gap-2'>
              {showAssign && (
                <Button
                  type='button'
                  disabled={!staffId || assigning}
                  onClick={() => onAssign(request, Number(staffId))}
                >
                  Assign
                </Button>
              )}
              {showReassign && (
                <Button
                  type='button'
                  variant='outline'
                  disabled={!staffId || Number(staffId) === assigned?.id || assigning}
                  onClick={() => onReassign(request, Number(staffId))}
                >
                  Reassign
                </Button>
              )}
              {canUnassign && assigned && (
                <Button type='button' variant='ghost' disabled={assigning} onClick={() => onUnassign(request)}>
                  Unassign
                </Button>
              )}
              {showAutoAssign && (
                <Button type='button' variant='outline' disabled={assigning} onClick={() => onAutoAssign(request)}>
                  Assign Automatically
                </Button>
              )}
            </div>

            {request.internal_notes && (
              <div>
                <p className='text-muted-foreground mb-1 text-sm'>Internal notes</p>
                <p className='text-sm whitespace-pre-wrap'>{request.internal_notes}</p>
              </div>
            )}
            {canAddNotes && (
              <Field>
                <FieldLabel>Add note</FieldLabel>
                <Textarea value={note} onChange={event => setNote(event.target.value)} rows={3} />
                <Button
                  type='button'
                  variant='outline'
                  className='mt-2 w-fit'
                  disabled={!note.trim()}
                  onClick={() => {
                    onNote(request, note.trim())
                    setNote('')
                  }}
                >
                  Add note
                </Button>
              </Field>
            )}

            {request.history && request.history.length > 0 && (
              <div>
                <p className='mb-2 text-sm font-medium'>History</p>
                <ol className='space-y-2 text-sm'>
                  {request.history.map(entry => (
                    <li key={entry.id} className='border-border/70 border-l-2 pl-3'>
                      <p className='font-medium'>{entry.action_label}</p>
                      <p className='text-muted-foreground'>
                        {entry.previous_value && entry.new_value
                          ? `${entry.previous_value} → ${entry.new_value}`
                          : entry.new_value || entry.previous_value || '—'}
                      </p>
                      <p className='text-muted-foreground text-xs'>
                        {entry.actor?.display_name || entry.actor?.name || 'System'} · {formatRelativeTime(entry.created_at) || '—'}
                      </p>
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}

export default MatchDetailSheet
