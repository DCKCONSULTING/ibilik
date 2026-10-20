const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'] as const

const startOfDay = (value: Date) => new Date(value.getFullYear(), value.getMonth(), value.getDate())

const isSameCalendarDay = (left: Date, right: Date) =>
  left.getFullYear() === right.getFullYear() && left.getMonth() === right.getMonth() && left.getDate() === right.getDate()

const isYesterdayOf = (value: Date, now: Date) => {
  const yesterday = new Date(now)

  yesterday.setDate(now.getDate() - 1)

  return isSameCalendarDay(value, yesterday)
}

const formatMonthDay = (value: Date, includeYear: boolean) => {
  const monthDay = `${MONTHS[value.getMonth()]} ${value.getDate()}`

  return includeYear ? `${monthDay}, ${value.getFullYear()}` : monthDay
}

export const toValidDate = (value: Date | string | number | null | undefined): Date | null => {
  if (value == null || value === '') return null

  const date = value instanceof Date ? value : new Date(value)

  return Number.isNaN(date.getTime()) ? null : date
}

export const formatRelativeTime = (value: Date | string | number | null | undefined, now: Date = new Date()): string => {
  const date = toValidDate(value)

  if (!date) return ''

  const diffMs = now.getTime() - date.getTime()

  if (diffMs < 60_000) return 'just now'

  const diffMinutes = Math.floor(diffMs / 60_000)

  if (diffMinutes < 60) {
    return diffMinutes === 1 ? '1 minute ago' : `${diffMinutes} minutes ago`
  }

  const diffHours = Math.floor(diffMinutes / 60)

  if (isSameCalendarDay(date, now)) {
    return diffHours === 1 ? '1 hour ago' : `${diffHours} hours ago`
  }

  if (isYesterdayOf(date, now)) return 'Yesterday'

  const diffDays = Math.floor((startOfDay(now).getTime() - startOfDay(date).getTime()) / 86_400_000)

  if (diffDays < 7) {
    return diffDays === 1 ? '1 day ago' : `${diffDays} days ago`
  }

  return formatMonthDay(date, date.getFullYear() !== now.getFullYear())
}

export const formatRelativeTimeCompact = (
  value: Date | string | number | null | undefined,
  now: Date = new Date()
): string => {
  const date = toValidDate(value)

  if (!date) return ''

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

export const formatDueAt = (value: Date | string | number | null | undefined, now: Date = new Date()): string => {
  const date = toValidDate(value)

  if (!date) return ''

  const hours = date.getHours().toString().padStart(2, '0')
  const minutes = date.getMinutes().toString().padStart(2, '0')
  const time = `${hours}:${minutes}`

  if (isSameCalendarDay(date, now)) return `Today ${time}`
  if (isYesterdayOf(date, now)) return `Yesterday ${time}`

  return `${formatMonthDay(date, date.getFullYear() !== now.getFullYear())} ${time}`
}

export const formatDueLabel = (
  value: Date | string | number | null | undefined,
  now: Date = new Date(),
  status?: string | null
): string => {
  const date = toValidDate(value)

  if (!date) return 'No due date'

  const overdue = status === 'overdue' || date.getTime() < now.getTime()
  const hours = date.getHours().toString().padStart(2, '0')
  const minutes = date.getMinutes().toString().padStart(2, '0')
  const time = `${hours}:${minutes}`

  if (overdue && status !== 'completed' && status !== 'cancelled') {
    const diffMs = now.getTime() - date.getTime()
    const diffHours = Math.max(1, Math.floor(diffMs / 3_600_000))

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
