// Third-party Imports
import { InboxIcon } from 'lucide-react'

// Type Imports
import type { Email } from '@/types/apps/mail-types'

// Component Imports
import { Button } from '@/components/ui/button'
import MailItem from './mail-item'

interface MailListProps {
  emails: Email[]
  selectedEmailId: string | null
  onEmailSelect: (email: Email) => void
  loading?: boolean
  error?: string | null
  onRetry?: () => void
}

const MailList = ({
  emails,
  selectedEmailId,
  onEmailSelect,
  loading = false,
  error = null,
  onRetry
}: MailListProps) => {
  if (loading && emails.length === 0) {
    return (
      <div className='text-muted-foreground flex min-h-0 flex-1 flex-col items-center justify-center gap-2 p-10 text-center'>
        <InboxIcon className='text-muted-foreground/40 size-9' />
        <p className='text-foreground text-sm font-medium'>Loading conversations...</p>
        <p className='text-xs'>Fetching the latest inbox from iBilik CRM.</p>
      </div>
    )
  }

  if (error && emails.length === 0) {
    return (
      <div className='flex min-h-0 flex-1 flex-col items-center justify-center gap-3 p-10 text-center'>
        <InboxIcon className='text-muted-foreground/40 size-9' />
        <div className='space-y-1'>
          <p className='text-foreground text-sm font-medium'>Unable to load conversations.</p>
          <p className='text-muted-foreground text-xs'>{error}</p>
        </div>
        {onRetry && (
          <Button type='button' variant='outline' size='sm' onClick={onRetry}>
            Try again
          </Button>
        )}
      </div>
    )
  }

  if (emails.length === 0) {
    return (
      <div className='text-muted-foreground flex min-h-0 flex-1 flex-col items-center justify-center gap-2 p-10 text-center'>
        <InboxIcon className='text-muted-foreground/40 size-9' />
        <p className='text-foreground text-sm font-medium'>No conversations</p>
        <p className='text-xs'>Nothing matches this source filter.</p>
      </div>
    )
  }

  return (
    <div className='min-h-0 flex-1 overflow-auto'>
      <div className='flex flex-col p-3 pt-0'>
        {emails.map(email => (
          <MailItem
            key={email.id}
            email={email}
            isSelected={selectedEmailId === email.id}
            onClick={() => onEmailSelect(email)}
          />
        ))}
      </div>
    </div>
  )
}

export default MailList
