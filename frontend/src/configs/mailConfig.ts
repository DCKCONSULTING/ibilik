// Type Imports
import type { EmailLabel, EmailStatus } from '@/types/apps/mail-types'

// Util Imports
import { formatRelativeTime } from '@/lib/datetime'

export const MAIL_CURRENT_USER = {
  name: 'You',
  email: 'you@example.com',
  avatar: undefined as string | undefined
}

export type MailNavStatusItem = {
  id: EmailStatus
  label: string
}

export type MailNavLabelItem = {
  id: EmailLabel
  label: string
}

export type MailNavLabelStyle = MailNavLabelItem & {
  color: string
}

export type MailNavStatusItemWithCount = MailNavStatusItem & {
  count: number
}

export type MailNavLabelItemWithCount = MailNavLabelItem & {
  count: number
}

export const MAIL_STATUS_NAV_ITEMS: MailNavStatusItem[] = [
  { id: 'inbox', label: 'Inbox' },
  { id: 'drafts', label: 'Drafts' },
  { id: 'sent', label: 'Sent' },
  { id: 'spam', label: 'Spam' },
  { id: 'trash', label: 'Trash' },
  { id: 'archive', label: 'Archive' }
]

export const MAIL_LABEL_NAV_ITEMS: MailNavLabelItem[] = [
  { id: 'social', label: 'Social' },
  { id: 'updates', label: 'Updates' },
  { id: 'forums', label: 'Forums' },
  { id: 'shopping', label: 'Shopping' },
  { id: 'promotions', label: 'Promotions' }
]

export const MAIL_LABEL_STYLES: MailNavLabelStyle[] = [
  { id: 'social', label: 'Social', color: 'bg-violet-500' },
  { id: 'updates', label: 'Updates', color: 'bg-teal-500' },
  { id: 'forums', label: 'Forums', color: 'bg-orange-500' },
  { id: 'shopping', label: 'Shopping', color: 'bg-lime-500' },
  { id: 'promotions', label: 'Promotions', color: 'bg-pink-500' }
]

export const getInitialsFromName = (name: string) => {
  return (
    name
      .split(' ')
      .filter(Boolean)
      .map(namePart => namePart[0])
      .join('')
      .slice(0, 2)
      .toUpperCase() || '?'
  )
}

export const MAIL_CHANNEL_LABELS: Record<string, string> = {
  website: 'Website',
  whatsapp: 'WhatsApp',
  facebook: 'Facebook Messenger'
}

export const formatMailDate = (date: Date, now: Date = new Date()) => formatRelativeTime(date, now)
