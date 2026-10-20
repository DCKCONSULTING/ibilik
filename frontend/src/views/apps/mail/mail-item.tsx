// Third-party Imports
import { GlobeIcon, MessageCircleIcon, MessagesSquareIcon } from 'lucide-react'

// Type Imports
import type { Email } from '@/types/apps/mail-types'

// Component Imports
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'

// Config Imports
import { getInitialsFromName, MAIL_CHANNEL_LABELS } from '@/configs/mailConfig'

// Hook Imports
import { useNow } from '@/hooks/use-now'

// Util Imports
import { formatRelativeTimeCompact } from '@/lib/datetime'
import { cn } from '@/lib/utils'

interface MailItemProps {
  email: Email
  isSelected: boolean
  onClick: () => void
}

const MailItem = ({ email, isSelected, onClick }: MailItemProps) => {
  const now = useNow()
  const relativeTime = formatRelativeTimeCompact(email.date, now)

  const ChannelIcon =
    email.channel === 'whatsapp' ? MessageCircleIcon : email.channel === 'facebook' ? MessagesSquareIcon : GlobeIcon

  const channelLabel = email.channel ? MAIL_CHANNEL_LABELS[email.channel] : null

  return (
    <button
      type='button'
      onClick={onClick}
      className={cn(
        'relative flex w-full items-start gap-3 overflow-hidden rounded-md border border-transparent p-3 text-left text-sm transition-colors',
        isSelected ? 'bg-accent border-border' : 'hover:bg-muted/40'
      )}
    >
      <Avatar className='size-9 shrink-0'>
        <AvatarImage src={email.avatar} alt={email.from} />
        <AvatarFallback>{getInitialsFromName(email.from)}</AvatarFallback>
      </Avatar>
      <div className='flex min-w-0 flex-1 flex-col gap-0.5'>
        <div className='flex items-baseline gap-3'>
          <span
            className={cn(
              'min-w-0 flex-1 truncate text-sm',
              !email.isRead ? 'text-foreground font-semibold' : 'text-foreground font-medium'
            )}
          >
            {email.from}
          </span>
          <time
            dateTime={email.date.toISOString()}
            className='text-foreground shrink-0 text-sm font-semibold tabular-nums'
          >
            {relativeTime}
          </time>
        </div>
        {channelLabel && (
          <span className='text-muted-foreground inline-flex min-w-0 items-center gap-1 text-xs'>
            <ChannelIcon className='size-3 shrink-0' />
            <span className='truncate'>{channelLabel}</span>
          </span>
        )}
        <p
          className={cn(
            'line-clamp-1 text-xs leading-snug',
            !email.isRead ? 'text-foreground font-medium' : 'text-muted-foreground'
          )}
        >
          {email.preview || email.subject}
        </p>
      </div>
    </button>
  )
}

export default MailItem
