import assert from 'node:assert/strict'
import test from 'node:test'

const staffLabel = staff => {
  if (!staff) return 'Unassigned'

  const name = staff.display_name || staff.name || staff.username
  const suffix = staff.is_active === false ? ' (inactive)' : ''

  return `${name}${suffix}`
}

const relatedRecordHref = item => {
  const related = item.related_record

  if (!related) return null
  if (related.kind === 'quote') return `/quotes/${related.id}`
  if (related.kind === 'booking') return `/bookings/${related.id}`
  if (related.kind === 'payment') return '/payments'
  if (related.kind === 'case') return `/opportunities/${related.id}`

  return null
}

const isHighlightedRequest = item =>
  item.priority === 'urgent' || Boolean(item.is_overdue && item.status !== 'resolved' && item.status !== 'cancelled')

const canShowAssign = (assigned, canAssign) => !assigned && canAssign
const canShowReassign = (assigned, canReassign) => Boolean(assigned) && canReassign
const canShowAutoAssign = canAssign => canAssign
const assignmentBadgeLabel = method => {
  if (method === 'automatic') return 'Auto-assigned'
  if (method === 'manual') return 'Manual'
  if (method === 'reassigned') return 'Reassigned'
  return null
}

test('staff names are shown and Unassigned is used when empty', () => {
  assert.equal(staffLabel({ display_name: 'Aiman Rahman', username: 'staff.lee' }), 'Aiman Rahman')
  assert.equal(staffLabel({ display_name: 'Sara Ali', is_active: false }), 'Sara Ali (inactive)')
  assert.equal(staffLabel(null), 'Unassigned')
})

test('related records link to existing CRM routes', () => {
  assert.equal(relatedRecordHref({ related_record: { kind: 'quote', id: 4 } }), '/quotes/4')
  assert.equal(relatedRecordHref({ related_record: { kind: 'booking', id: 9 } }), '/bookings/9')
  assert.equal(relatedRecordHref({ related_record: { kind: 'case', id: 3 } }), '/opportunities/3')
  assert.equal(relatedRecordHref({ related_record: { kind: 'payment', id: 2 } }), '/payments')
  assert.equal(relatedRecordHref({ related_record: null }), null)
})

test('urgent and overdue requests are highlighted', () => {
  assert.equal(isHighlightedRequest({ priority: 'urgent', is_overdue: false, status: 'new' }), true)
  assert.equal(isHighlightedRequest({ priority: 'normal', is_overdue: true, status: 'assigned' }), true)
  assert.equal(isHighlightedRequest({ priority: 'normal', is_overdue: true, status: 'resolved' }), false)
})

test('assignment controls follow permission and current assignee', () => {
  assert.equal(canShowAssign(null, true), true)
  assert.equal(canShowAssign({ id: 1 }, true), false)
  assert.equal(canShowReassign({ id: 1 }, true), true)
  assert.equal(canShowReassign(null, true), false)
  assert.equal(canShowAssign(null, false), false)
  assert.equal(canShowAutoAssign(true), true)
  assert.equal(canShowAutoAssign(false), false)
})

test('assignment badges use Automatic and Manual labels', () => {
  assert.equal(assignmentBadgeLabel('automatic'), 'Auto-assigned')
  assert.equal(assignmentBadgeLabel('manual'), 'Manual')
  assert.equal(assignmentBadgeLabel('reassigned'), 'Reassigned')
  assert.equal(assignmentBadgeLabel(null), null)
})
