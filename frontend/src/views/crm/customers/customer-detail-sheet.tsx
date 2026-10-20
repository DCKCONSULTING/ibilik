'use client'

import { useEffect, useState } from 'react'

import Link from 'next/link'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { isApiError } from '@/lib/api'
import { customersApi } from '@/lib/customers/api'
import type { Customer } from '@/lib/customers/types'
import { channelLabel, formatLastContact } from '@/lib/customers/validation'

type CustomerDetailSheetProps = {
  customer: Customer | null
  onOpenChange: (open: boolean) => void
}

const senderLabel = (value: string) => {
  if (value === 'bot') return 'AI Bot'
  if (value === 'staff') return 'Staff'
  if (value === 'system') return 'System'

  return 'Customer'
}

const CustomerDetailSheet = ({ customer, onOpenChange }: CustomerDetailSheetProps) => {
  const customerId = customer?.id ?? null
  const [detail, setDetail] = useState<Customer | null>(null)
  const visible = detail?.id === customerId ? detail : customer

  useEffect(() => {
    if (!customerId) return

    let mounted = true

    customersApi
      .get(customerId)
      .then(next => {
        if (!mounted) return
        setDetail(next)
      })
      .catch(error => {
        if (!mounted) return
        toast.error(isApiError(error) ? error.message : 'Unable to load customer details.')
      })

    return () => {
      mounted = false
    }
  }, [customerId])

  return (
    <Sheet open={customer !== null} onOpenChange={open => !open && onOpenChange(false)}>
      <SheetContent className='overflow-y-auto sm:max-w-lg'>
        <SheetHeader>
          <SheetTitle>{visible?.name ?? 'Customer'}</SheetTitle>
        </SheetHeader>
        {visible && (
          <div className='flex flex-col gap-6 px-4 pb-6'>
            <dl className='grid gap-3 text-sm sm:grid-cols-2'>
              <div>
                <dt className='text-muted-foreground'>Phone</dt>
                <dd className='font-medium'>{visible.phone || '—'}</dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Email</dt>
                <dd className='font-medium'>{visible.email || '—'}</dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Status</dt>
                <dd className='font-medium capitalize'>{visible.status}</dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Last contact</dt>
                <dd className='font-medium'>{formatLastContact(visible.last_contact_at)}</dd>
              </div>
            </dl>

            <section className='space-y-2'>
              <h3 className='font-medium'>Sources</h3>
              <div className='flex flex-wrap gap-1.5'>
                {(visible.sources ?? []).length === 0 ? (
                  <p className='text-muted-foreground text-sm'>No channel history yet.</p>
                ) : (
                  visible.sources.map(source => (
                    <Badge key={source} variant='outline'>
                      {channelLabel(source)}
                    </Badge>
                  ))
                )}
              </div>
            </section>

            <section className='space-y-2'>
              <h3 className='font-medium'>Channel identities</h3>
              {(visible.identities ?? []).length === 0 ? (
                <p className='text-muted-foreground text-sm'>No stored channel identities.</p>
              ) : (
                <ul className='space-y-2'>
                  {visible.identities?.map(identity => (
                    <li key={identity.id} className='rounded-md border px-3 py-2 text-sm'>
                      <p className='font-medium'>{channelLabel(identity.channel)}</p>
                      <p className='text-muted-foreground'>{identity.identifier}</p>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className='space-y-2'>
              <h3 className='font-medium'>Cases</h3>
              {(visible.cases ?? []).length === 0 ? (
                <p className='text-muted-foreground text-sm'>No cases yet.</p>
              ) : (
                <ul className='space-y-2'>
                  {visible.cases?.map(item => (
                    <li key={item.id}>
                      <Link
                        href={`/opportunities/${item.id}`}
                        className='hover:bg-muted/40 flex items-center justify-between gap-3 rounded-md border px-3 py-2 text-sm'
                      >
                        <span>
                          <span className='font-medium'>{item.case_number}</span>
                          <span className='text-muted-foreground ml-2'>{item.title}</span>
                        </span>
                        <Badge variant='outline'>{item.stage_label}</Badge>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className='space-y-3'>
              <h3 className='font-medium'>Conversation history</h3>
              {(visible.timeline ?? []).length === 0 ? (
                <p className='text-muted-foreground text-sm'>No messages yet.</p>
              ) : (
                <ol className='space-y-3'>
                  {visible.timeline?.map(item => (
                    <li key={item.id} className='rounded-md border px-3 py-2'>
                      <div className='mb-1 flex flex-wrap items-center gap-2 text-xs'>
                        <Badge variant='outline'>{channelLabel(item.channel)}</Badge>
                        <span className='font-medium'>{senderLabel(item.sender_type)}</span>
                        <span className='text-muted-foreground ml-auto'>{formatLastContact(item.created_at)}</span>
                      </div>
                      <p className='text-sm whitespace-pre-wrap'>{item.content}</p>
                    </li>
                  ))}
                </ol>
              )}
            </section>
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}

export default CustomerDetailSheet
