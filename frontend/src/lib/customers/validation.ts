import type { CustomerDraft } from '@/lib/customers/types'

export type CustomerFieldErrors = Partial<Record<keyof CustomerDraft, string>>

export const emptyCustomerDraft = (): CustomerDraft => ({
  name: '',
  email: '',
  phone: '',
  status: 'lead',
  notes: '',
  property_id: ''
})

export const validateCustomerDraft = (draft: CustomerDraft): CustomerFieldErrors => {
  const errors: CustomerFieldErrors = {}

  if (!draft.name.trim()) errors.name = 'Name is required.'

  const email = draft.email.trim()
  const phone = draft.phone.trim()

  if (email && !email.includes('@')) errors.email = 'Enter a valid email address.'
  if (!email && !phone) errors.phone = 'A phone number or email address is required.'

  return errors
}

export const formatLastContact = (value: string | null | undefined): string => {
  if (!value) return '—'

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) return '—'

  return date.toLocaleString()
}

export const channelLabel = (channel: string): string => {
  if (channel === 'whatsapp') return 'WhatsApp'
  if (channel === 'facebook') return 'Facebook Messenger'
  if (channel === 'website') return 'Website'

  return channel
}
