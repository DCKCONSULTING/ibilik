// Type Imports
import type { ThreadMessage } from '@/types/apps/mail-types'

// Component Imports
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'

// Config Imports
import { formatMailDate, getInitialsFromName, MAIL_CHANNEL_LABELS } from '@/configs/mailConfig'

export const MailThreadMessage = ({
  message,
  avatar,
  variant = 'card'
}: {
  message: ThreadMessage
  avatar?: string
  variant?: 'card' | 'plain'
}) => {
  // Props

  // Vars
  const content = (
    <>
      <div className='mb-4 flex items-start gap-3'>
        <Avatar className='size-9 shrink-0'>
          <AvatarImage src={avatar} alt={message.from} />
          <AvatarFallback>{getInitialsFromName(message.from)}</AvatarFallback>
        </Avatar>
        <div className='flex-1'>
          <div className='flex items-center justify-between gap-2'>
            <span className='text-sm font-semibold'>{message.from}</span>
            <span className='text-muted-foreground shrink-0 text-xs'>{formatMailDate(message.date)}</span>
          </div>
          <div className='text-muted-foreground flex flex-wrap items-center gap-2 text-xs'>
            {message.senderType === 'bot' && <span>AI Bot</span>}
            {message.senderType === 'staff' && <span>Staff</span>}
            {message.senderType === 'customer' && <span>Customer</span>}
            {message.channel && <span>{MAIL_CHANNEL_LABELS[message.channel] ?? message.channel}</span>}
            {message.fromEmail && <span>{message.fromEmail}</span>}
            {message.status === 'failed' && <span>Failed to send</span>}
          </div>
        </div>
      </div>
      <div className='text-foreground/80 text-sm whitespace-pre-wrap'>{message.body}</div>
    </>
  )

  if (variant === 'plain') {
    return <div className='px-3'>{content}</div>
  }

  return <div className='border-border/60 bg-muted/20 rounded-lg border p-4'>{content}</div>
}
