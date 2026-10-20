import type { InboxConversation, InboxMessage } from '@/lib/inbox/types'
import { toValidDate } from '@/lib/datetime'
import type { Email, ThreadMessage } from '@/types/apps/mail-types'

const fallbackDate = (value: Date | string | number | null | undefined) => toValidDate(value) ?? new Date()

export const conversationLastMessageAt = (conversation: InboxConversation) =>
  conversation.last_message?.created_at || conversation.last_message_at || conversation.updated_at

export const conversationLastMessagePreview = (conversation: InboxConversation) =>
  conversation.last_message?.content || conversation.last_message_preview || ''

export const conversationCustomerName = (conversation: InboxConversation) => {
  const name = conversation.customer?.name?.trim()

  return name || 'Unknown customer'
}

export const conversationToEmail = (conversation: InboxConversation, messages: ThreadMessage[] = []): Email => {
  const customer = conversation.customer
  const preview = conversationLastMessagePreview(conversation)

  return {
    id: String(conversation.id),
    from: conversationCustomerName(conversation),
    fromEmail: customer?.email || customer?.phone || '',
    avatar: undefined,
    subject: conversation.subject || preview || `${conversation.channel} conversation`,
    preview,
    body: preview,
    date: fallbackDate(conversationLastMessageAt(conversation)),
    isRead: !conversation.is_unread,
    isStarred: false,
    labels: [],
    status: 'inbox',
    thread: { messages },
    channel: conversation.channel,
    replyChannels: conversation.reply_channels,
    conversationId: conversation.id,
    propertyName: conversation.property?.name
  }
}

export const messageToThread = (message: InboxMessage): ThreadMessage => ({
  id: String(message.id),
  from:
    message.sender_type === 'bot'
      ? 'AI Bot'
      : message.sender_type === 'staff'
        ? message.sender_name || 'Staff'
        : message.sender_name || 'Customer',
  fromEmail: message.sender_identifier,
  body: message.content,
  date: fallbackDate(message.created_at || message.received_at || message.sent_at),
  isFromMe: message.direction === 'outbound' || message.sender_type === 'staff',
  channel: message.channel,
  senderType: message.sender_type,
  status: message.status
})
