export type CustomerStatus = 'lead' | 'active' | 'archived'

export type Channel = 'website' | 'whatsapp' | 'facebook'

export type CustomerIdentity = {
  id: number
  channel: Channel
  identifier: string
  identifier_type: string
  display_name: string
}

export type CustomerProperty = {
  id: number
  name: string
}

export type CustomerCaseSummary = {
  id: number
  case_number: string
  title: string
  stage: string
  stage_label: string
  updated_at: string | null
}

export type Customer = {
  id: number
  name: string
  email: string
  phone: string
  status: CustomerStatus
  notes?: string
  sources: Channel[]
  properties: CustomerProperty[]
  last_contact_at: string | null
  reply_channels: Channel[]
  identities?: CustomerIdentity[]
  created_at?: string | null
  updated_at?: string | null
  timeline?: CustomerTimelineItem[]
  conversations?: ConversationSummary[]
  cases?: CustomerCaseSummary[]
}

export type CustomerTimelineItem = {
  id: number
  conversation_id: number
  channel: Channel
  direction: 'inbound' | 'outbound'
  sender_type: 'customer' | 'staff' | 'bot' | 'system'
  sender_name: string
  content: string
  created_at: string | null
  status: string
}

export type ConversationSummary = {
  id: number
  channel: Channel
  status: string
  last_message_preview: string
  last_message_at: string | null
  unread_count: number
  property: CustomerProperty | null
}

export type CustomerListResponse = {
  resource: string
  count: number
  page: number
  page_size: number
  has_next: boolean
  results: Customer[]
}

export type CustomerDraft = {
  name: string
  email: string
  phone: string
  status: CustomerStatus
  notes: string
  property_id: string
}
