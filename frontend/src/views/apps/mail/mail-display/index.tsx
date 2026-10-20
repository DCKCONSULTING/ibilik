'use client'

// Type Imports
import type { Email } from '@/types/apps/mail-types'

// Component Imports
import { MailDisplayContent } from './mail-display-content'

import type { Channel } from '@/lib/customers/types'

export interface MailDisplayProps {
  email: Email | null
  sending?: boolean
  hasMoreMessages?: boolean
  onLoadEarlier?: () => void
  onSendReply?: (content: string, channel: Channel) => Promise<unknown>
}

export const MailDisplay = ({ email, sending, hasMoreMessages, onLoadEarlier, onSendReply }: MailDisplayProps) => {
  if (!email) {
    return (
      <div className='text-muted-foreground flex h-full flex-col items-center justify-center gap-2 p-10 text-center'>
        <p className='text-foreground text-sm font-medium'>No conversation selected</p>
        <p className='text-xs'>Choose a conversation from the list to read it here.</p>
      </div>
    )
  }

  return (
    <MailDisplayContent
      key={email.id}
      email={email}
      sending={sending}
      hasMoreMessages={hasMoreMessages}
      onLoadEarlier={onLoadEarlier}
      onSendReply={onSendReply}
    />
  )
}

export default MailDisplay
