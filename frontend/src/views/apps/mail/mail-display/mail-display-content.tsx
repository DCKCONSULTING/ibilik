'use client'

// React Imports
import { useState } from 'react'

// Third-party Imports
import { ChevronDown, SendIcon } from 'lucide-react'

// Type Imports
import { toast } from 'sonner'

import type { Channel } from '@/lib/customers/types'
import type { Email, ThreadMessage } from '@/types/apps/mail-types'

// Component Imports
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { MailThreadMessage } from './mail-thread-message'

// Config Imports
import { formatMailDate, getInitialsFromName, MAIL_CHANNEL_LABELS, MAIL_CURRENT_USER } from '@/configs/mailConfig'

// Util Imports
import { cn } from '@/lib/utils'

export const MailDisplayContent = ({
  email,
  sending = false,
  hasMoreMessages = false,
  onLoadEarlier,
  onSendReply
}: {
  email: Email
  sending?: boolean
  hasMoreMessages?: boolean
  onLoadEarlier?: () => void
  onSendReply?: (content: string, channel: Channel) => Promise<unknown>
}) => {
  // States
  const [replyMessageBody, setReplyMessageBody] = useState(() => (email.status === 'drafts' ? email.body : ''))
  const [isEarlierMessagesExpanded, setIsEarlierMessagesExpanded] = useState(true)
  const [replyChannel, setReplyChannel] = useState<Channel | ''>(email.replyChannels?.[0] ?? '')
  const [sendError, setSendError] = useState<string | null>(null)

  // Vars
  const threadMessages = email.thread.messages
  const earlierThreadMessages = threadMessages.slice(0, -1)
  const latestThreadMessage = threadMessages[threadMessages.length - 1]
  const earlierMessageCount = earlierThreadMessages.length

  const isDraft = email.status === 'drafts'
  const isSent = email.status === 'sent'

  const recipientName = isSent || isDraft ? (email.to ?? 'Unknown') : email.from
  const recipientEmail = isSent || isDraft ? (email.toEmail ?? '') : email.fromEmail

  const getThreadMessageAvatar = (message: ThreadMessage) => {
    if (message.isFromMe) {
      return MAIL_CURRENT_USER.avatar
    }

    if (message.from === email.from) {
      return email.avatar
    }

    return undefined
  }

  return (
    <div className='flex h-full min-h-0 flex-col'>
      <div className='flex min-h-0 flex-1 flex-col overflow-hidden'>
        <div className='border-border border-b p-3 max-lg:pt-12'>
          <div className='flex items-start justify-between gap-4'>
            <div className='flex min-w-0 flex-1 items-start gap-3'>
              <Avatar size='lg' className='shrink-0 max-md:hidden'>
                {!isSent && !isDraft && <AvatarImage src={email.avatar} alt={email.from} />}
                <AvatarFallback>{getInitialsFromName(recipientName)}</AvatarFallback>
              </Avatar>
              <div className='min-w-0 flex-1'>
                <h2 className='text-foreground line-clamp-2 text-base leading-snug font-medium tracking-tight md:font-semibold'>
                  {email.subject}
                </h2>
                <div className='mt-1 flex flex-wrap items-center gap-2 text-xs'>
                  {email.channel && <Badge variant='outline'>{MAIL_CHANNEL_LABELS[email.channel]}</Badge>}
                  {email.propertyName && <Badge variant='outline'>{email.propertyName}</Badge>}
                </div>
                {isSent || isDraft ? (
                  <>
                    <p className='text-foreground mt-1 text-sm font-medium'>
                      <span className='text-muted-foreground font-normal'>To: </span>
                      {recipientName}
                    </p>
                    {recipientEmail && <p className='text-muted-foreground mt-0.5 text-xs'>{recipientEmail}</p>}
                  </>
                ) : (
                  <>
                    <p className='text-foreground mt-1 text-sm font-medium'>{email.from}</p>
                    <p className='text-muted-foreground mt-0.5 text-xs'>Reply-To: {email.fromEmail}</p>
                  </>
                )}
              </div>
            </div>
            <span className='text-muted-foreground shrink-0 pt-0.5 text-xs'>{formatMailDate(email.date)}</span>
          </div>
        </div>

        <div className='flex-1 overflow-auto p-3'>
          <div className='flex flex-col gap-5'>
            {(earlierMessageCount > 0 || hasMoreMessages) && (
              <button
                type='button'
                className='text-muted-foreground hover:text-foreground flex w-full items-center gap-2 text-sm font-medium transition-colors'
                onClick={() => {
                  setIsEarlierMessagesExpanded(currentValue => !currentValue)
                  if (hasMoreMessages) onLoadEarlier?.()
                }}
              >
                <ChevronDown className={cn('size-4 transition-transform', isEarlierMessagesExpanded && 'rotate-180')} />
                {hasMoreMessages
                  ? 'Load earlier messages'
                  : `${earlierMessageCount} earlier ${earlierMessageCount === 1 ? 'message' : 'messages'}`}
              </button>
            )}

            {isEarlierMessagesExpanded &&
              earlierThreadMessages.map(threadMessage => (
                <MailThreadMessage
                  key={threadMessage.id}
                  message={threadMessage}
                  avatar={getThreadMessageAvatar(threadMessage)}
                />
              ))}

            {latestThreadMessage && (
              <MailThreadMessage
                message={latestThreadMessage}
                avatar={getThreadMessageAvatar(latestThreadMessage)}
                variant='plain'
              />
            )}
          </div>
        </div>

        <div className='border-border mt-auto border-t p-3'>
          <form
            onSubmit={async event => {
              event.preventDefault()

              if (!onSendReply || !replyChannel || !replyMessageBody.trim()) return

              setSendError(null)

              try {
                await onSendReply(replyMessageBody.trim(), replyChannel)
                setReplyMessageBody('')
              } catch (error) {
                const message = error instanceof Error ? error.message : 'Unable to send message. Please try again.'

                setSendError(message)
                toast.error(message)
              }
            }}
          >
            <div className='border-border bg-muted/20 overflow-hidden rounded-lg border'>
              <Textarea
                className='resize-none rounded-none border-0 bg-transparent p-2 text-sm shadow-none focus-visible:ring-0 max-md:min-h-10 md:px-4 md:py-3'
                placeholder={
                  email.replyChannels && email.replyChannels.length > 0
                    ? `Reply to ${recipientName}...`
                    : 'No reachable reply channel for this customer.'
                }
                value={replyMessageBody}
                onChange={event => setReplyMessageBody(event.target.value)}
                disabled={!email.replyChannels?.length}
              />
              <div className='border-border flex flex-wrap items-center justify-between gap-2 border-t p-2 md:px-4 md:py-2.5'>
                <div className='flex items-center gap-2'>
                  <label className='text-muted-foreground text-sm'>Reply via</label>
                  <Select
                    value={replyChannel || null}
                    onValueChange={value => value && setReplyChannel(value as Channel)}
                    disabled={!email.replyChannels?.length}
                  >
                    <SelectTrigger size='sm'>
                      <SelectValue placeholder='No channel' />
                    </SelectTrigger>
                    <SelectContent>
                      {(email.replyChannels ?? []).map(channel => (
                        <SelectItem key={channel} value={channel}>
                          {MAIL_CHANNEL_LABELS[channel]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <Button
                  type='submit'
                  variant='secondary'
                  size='sm'
                  title='Send reply'
                  className='gap-1.5 rounded-lg px-4'
                  disabled={sending || !replyMessageBody.trim() || !replyChannel}
                >
                  {sending ? 'Sending…' : 'Send'}
                  <SendIcon className='size-4' />
                </Button>
              </div>
            </div>
            {sendError && <p className='text-destructive mt-2 text-sm'>{sendError}</p>}
          </form>
        </div>
      </div>
    </div>
  )
}
