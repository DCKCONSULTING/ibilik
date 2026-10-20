import { api } from '@/lib/api'
import type { Channel } from '@/lib/customers/types'
import type { ConversationListResponse, InboxConversation, InboxMessage, MessageListResponse } from '@/lib/inbox/types'

export const inboxApi = {
  listConversations(query?: Record<string, string | number | boolean | undefined>) {
    return api.get<ConversationListResponse>('/api/conversations/', { query })
  },
  getConversation(id: number) {
    return api.get<InboxConversation>(`/api/conversations/${id}/`)
  },
  listMessages(id: number, query?: Record<string, string | number | boolean | undefined>) {
    return api.get<MessageListResponse>(`/api/conversations/${id}/messages/`, { query })
  },
  sendMessage(id: number, payload: { content: string; channel: Channel }) {
    return api.post<InboxMessage>(`/api/conversations/${id}/messages/`, payload)
  },
  markRead(id: number) {
    return api.post<InboxConversation>(`/api/conversations/${id}/read/`)
  }
}
