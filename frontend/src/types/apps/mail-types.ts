export type MailChannel = 'website' | 'whatsapp' | 'facebook'

export type MailSenderType = 'customer' | 'staff' | 'bot' | 'system'

export type ThreadMessage = {
  id: string
  from: string
  fromEmail: string
  body: string
  date: Date
  isFromMe?: boolean
  channel?: MailChannel
  senderType?: MailSenderType
  status?: string
}

export type EmailLabel = 'social' | 'updates' | 'forums' | 'shopping' | 'promotions'

export type EmailStatus = 'inbox' | 'sent' | 'drafts' | 'spam' | 'trash' | 'archive'

export type Email = {
  id: string
  from: string
  fromEmail: string
  to?: string
  toEmail?: string
  cc?: string
  bcc?: string
  avatar?: string
  subject: string
  preview: string
  body: string
  date: Date
  isRead: boolean
  isStarred: boolean
  labels: EmailLabel[]
  status: EmailStatus
  thread: {
    messages: ThreadMessage[]
  }
  channel?: MailChannel
  replyChannels?: MailChannel[]
  conversationId?: number
  propertyName?: string
  hasMoreMessages?: boolean
}

export type MailData = {
  emails: Email[]
}

export type MailFilterTab = 'all' | 'unread'

export type MailNavType = 'status' | 'label'
