import assert from 'node:assert/strict'
import test from 'node:test'

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

const startOfDay = value => new Date(value.getFullYear(), value.getMonth(), value.getDate())

const isSameCalendarDay = (left, right) =>
  left.getFullYear() === right.getFullYear() && left.getMonth() === right.getMonth() && left.getDate() === right.getDate()

const isYesterdayOf = (value, now) => {
  const yesterday = new Date(now)

  yesterday.setDate(now.getDate() - 1)

  return isSameCalendarDay(value, yesterday)
}

const formatMonthDay = (value, includeYear) => {
  const monthDay = `${MONTHS[value.getMonth()]} ${value.getDate()}`

  return includeYear ? `${monthDay}, ${value.getFullYear()}` : monthDay
}

const formatRelativeTime = (value, now = new Date()) => {
  const date = value instanceof Date ? value : new Date(value)
  const diffMs = now.getTime() - date.getTime()

  if (diffMs < 60_000) return 'just now'

  const diffMinutes = Math.floor(diffMs / 60_000)

  if (diffMinutes < 60) return diffMinutes === 1 ? '1 minute ago' : `${diffMinutes} minutes ago`

  const diffHours = Math.floor(diffMinutes / 60)

  if (isSameCalendarDay(date, now)) return diffHours === 1 ? '1 hour ago' : `${diffHours} hours ago`

  if (isYesterdayOf(date, now)) return 'Yesterday'

  const diffDays = Math.floor((startOfDay(now).getTime() - startOfDay(date).getTime()) / 86_400_000)

  if (diffDays < 7) return diffDays === 1 ? '1 day ago' : `${diffDays} days ago`

  return formatMonthDay(date, date.getFullYear() !== now.getFullYear())
}

const formatRelativeTimeCompact = (value, now = new Date()) => {
  const date = value instanceof Date ? value : new Date(value)
  const diffMs = now.getTime() - date.getTime()

  if (diffMs < 60_000) return 'just now'

  const diffMinutes = Math.floor(diffMs / 60_000)

  if (diffMinutes < 60) return `${diffMinutes}m`

  const diffHours = Math.floor(diffMinutes / 60)

  if (isSameCalendarDay(date, now)) return `${diffHours}h`

  if (isYesterdayOf(date, now)) return 'Yesterday'

  const diffDays = Math.floor((startOfDay(now).getTime() - startOfDay(date).getTime()) / 86_400_000)

  if (diffDays < 7) return `${diffDays}d`

  return formatMonthDay(date, date.getFullYear() !== now.getFullYear())
}

const now = new Date('2026-09-06T12:00:00')

test('relative time uses last-message friendly labels', () => {
  assert.equal(formatRelativeTime(new Date(now.getTime() - 10_000), now), 'just now')
  assert.equal(formatRelativeTime(new Date(now.getTime() - 5 * 60_000), now), '5 minutes ago')
  assert.equal(formatRelativeTime(new Date(now.getTime() - 33 * 60_000), now), '33 minutes ago')
  assert.equal(formatRelativeTime(new Date(now.getTime() - 60 * 60_000), now), '1 hour ago')
  assert.equal(formatRelativeTime(new Date(now.getTime() - 2 * 60 * 60_000), now), '2 hours ago')
  assert.equal(formatRelativeTime(new Date('2026-09-05T18:00:00'), now), 'Yesterday')
  assert.equal(formatRelativeTime(new Date('2026-09-04T12:00:00'), now), '2 days ago')
  assert.equal(formatRelativeTime(new Date('2026-08-20T12:00:00'), now), 'Aug 20')
  assert.equal(formatRelativeTime(new Date('2025-09-04T12:00:00'), now), 'Sep 4, 2025')
})

test('compact relative time stays scannable in the conversation list', () => {
  assert.equal(formatRelativeTimeCompact(new Date(now.getTime() - 33 * 60_000), now), '33m')
  assert.equal(formatRelativeTimeCompact(new Date(now.getTime() - 2 * 60 * 60_000), now), '2h')
  assert.equal(formatRelativeTimeCompact(new Date('2026-09-05T18:00:00'), now), 'Yesterday')
})

const formatDueLabel = (value, now = new Date(), status) => {
  const date = value instanceof Date ? value : new Date(value)

  if (Number.isNaN(date.getTime())) return 'No due date'

  const overdue = status === 'overdue' || date.getTime() < now.getTime()
  const hours = date.getHours().toString().padStart(2, '0')
  const minutes = date.getMinutes().toString().padStart(2, '0')
  const time = `${hours}:${minutes}`

  if (overdue && status !== 'completed' && status !== 'cancelled') {
    const diffHours = Math.max(1, Math.floor((now.getTime() - date.getTime()) / 3_600_000))

    if (diffHours < 24) return `Overdue by ${diffHours} ${diffHours === 1 ? 'hour' : 'hours'}`

    const diffDays = Math.floor(diffHours / 24)

    return `Overdue by ${diffDays} ${diffDays === 1 ? 'day' : 'days'}`
  }

  const tomorrow = new Date(now)

  tomorrow.setDate(now.getDate() + 1)

  if (isSameCalendarDay(date, now)) return `Due today ${time}`
  if (isSameCalendarDay(date, tomorrow)) return `Due tomorrow ${time}`

  return formatMonthDay(date, date.getFullYear() !== now.getFullYear())
}

test('due labels distinguish overdue, today, and later dates', () => {
  assert.equal(formatDueLabel(new Date('2026-09-06T10:00:00'), now, 'overdue'), 'Overdue by 2 hours')
  assert.equal(formatDueLabel(new Date('2026-09-06T16:00:00'), now, 'pending'), 'Due today 16:00')
  assert.equal(formatDueLabel(new Date('2026-09-07T09:00:00'), now, 'pending'), 'Due tomorrow 09:00')
  assert.equal(formatDueLabel(new Date('2026-09-10T14:00:00'), now, 'pending'), 'Sep 10')
})
