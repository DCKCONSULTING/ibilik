import type { Channel, Customer } from '@/lib/customers/types'

export type SenderType = 'customer' | 'staff' | 'bot' | 'system'
export type MessageDirection = 'inbound' | 'outbound'
export type MessageStatus = 'pending' | 'sent' | 'delivered' | 'read' | 'failed' | 'received'

export type InboxMessage = {
  id: number
  conversation_id: number
  channel: Channel
  direction: MessageDirection
  sender_type: SenderType
  sender_name: string
  sender_identifier: string
  recipient_identifier: string
  content: string
  attachments: Array<Record<string, unknown>>
  external_message_id: string
  status: MessageStatus
  error_message: string
  created_by_id: number | null
  received_at: string | null
  sent_at: string | null
  created_at: string | null
  updated_at: string | null
}

export type ConversationLastMessage = {
  content: string
  created_at: string | null
}

export type InboxConversationCustomer = Pick<Customer, 'id' | 'name'> & Partial<Omit<Customer, 'id' | 'name'>>

export type InboxConversation = {
  id: number
  channel: Channel
  external_conversation_id: string
  status: string
  subject: string
  last_message?: ConversationLastMessage | null
  last_message_preview: string
  last_message_at: string | null
  unread_count: number
  is_unread: boolean
  property: { id: number; name: string } | null
  reply_channels: Channel[]
  customer?: InboxConversationCustomer
  created_at: string | null
  updated_at: string | null
}

export type ConversationListResponse = {
  resource: string
  count: number
  page: number
  page_size: number
  has_next: boolean
  results: InboxConversation[]
}

export type MessageListResponse = {
  resource: string
  conversation_id: number
  count: number
  page: number
  page_size: number
  has_next: boolean
  results: InboxMessage[]
}
