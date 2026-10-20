import type { MatchRequest, MatchStaff } from '@/lib/match/types'

export const staffLabel = (staff: MatchStaff | null | undefined) => {
  if (!staff) return 'Unassigned'

  const name = staff.display_name || staff.name || staff.username
  const suffix = staff.is_active === false ? ' (inactive)' : ''

  return `${name}${suffix}`
}

export const relatedRecordHref = (item: MatchRequest) => {
  const related = item.related_record

  if (!related) return null
  if (related.kind === 'quote') return `/quotes/${related.id}`
  if (related.kind === 'booking') return `/bookings/${related.id}`
  if (related.kind === 'payment') return '/payments'
  if (related.kind === 'case') return `/opportunities/${related.id}`

  return null
}

export const isHighlightedRequest = (item: Pick<MatchRequest, 'priority' | 'is_overdue' | 'status'>) =>
  item.priority === 'urgent' || Boolean(item.is_overdue && item.status !== 'resolved' && item.status !== 'cancelled')

export const canShowAssign = (assigned: MatchStaff | null | undefined, canAssign: boolean) =>
  !assigned && canAssign

export const canShowReassign = (assigned: MatchStaff | null | undefined, canReassign: boolean) =>
  Boolean(assigned) && canReassign

export const canShowAutoAssign = (canAssign: boolean) => canAssign

export const assignmentBadgeLabel = (method: string | null | undefined) => {
  if (method === 'automatic') return 'Auto-assigned'
  if (method === 'manual') return 'Manual'
  if (method === 'reassigned') return 'Reassigned'
  return null
}

export const emptyMatchSummary = () => ({
  new: 0,
  unassigned: 0,
  assigned: 0,
  in_progress: 0,
  urgent: 0,
  resolved: 0,
  new_unassigned_count: 0
})
