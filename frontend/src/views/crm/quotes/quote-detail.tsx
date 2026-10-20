'use client'

import { useEffect, useState } from 'react'

import Link from 'next/link'
import { useParams } from 'next/navigation'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { isApiError } from '@/lib/api'
import type { Customer } from '@/lib/customers/types'
import { formatDueAt, formatRelativeTime } from '@/lib/datetime'
import { paymentsApi } from '@/lib/payments/api'
import type { Payment } from '@/lib/payments/types'
import { quotesApi } from '@/lib/quotes/api'
import type { Quote } from '@/lib/quotes/types'
import { cn } from '@/lib/utils'
import CustomerDetailSheet from '@/views/crm/customers/customer-detail-sheet'

const statusClass = (status: string) => {
  if (status === 'expired' || status === 'rejected') return 'text-destructive'
  if (status === 'accepted') return 'border-transparent bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'

  return ''
}

const QuoteDetailView = () => {
  const params = useParams<{ id: string }>()
  const quoteId = Number(params.id)
  const validId = Number.isInteger(quoteId) && quoteId > 0
  const [quote, setQuote] = useState<Quote | null>(null)
  const [payments, setPayments] = useState<Payment[]>([])
  const [loading, setLoading] = useState(validId)
  const [error, setError] = useState<string | null>(validId ? null : 'Quotation not found.')
  const [customer, setCustomer] = useState<Customer | null>(null)

  const loadQuote = () =>
    quotesApi.get(quoteId).then(async payload => {
      setQuote(payload)
      setError(null)

      try {
        const paymentList = await paymentsApi.list({ case: payload.case.id, page_size: 50, status: 'all' })

        setPayments(paymentList.results)
      } catch {
        setPayments([])
      }

      return payload
    })

  useEffect(() => {
    if (!validId) return

    let mounted = true

    loadQuote()
      .catch(err => {
        if (!mounted) return

        setQuote(null)
        setError(isApiError(err) ? err.message : 'Unable to load this quotation.')
      })
      .finally(() => {
        if (!mounted) return

        setLoading(false)
      })

    return () => {
      mounted = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [quoteId, validId])

  const retry = () => {
    setLoading(true)
    void loadQuote()
      .catch(err => {
        setQuote(null)
        setError(isApiError(err) ? err.message : 'Unable to load this quotation.')
      })
      .finally(() => setLoading(false))
  }

  if (loading) {
    return <p className='text-muted-foreground text-sm'>Loading quotation…</p>
  }

  if (error || !quote) {
    return (
      <div className='flex flex-col gap-4'>
        <Button render={<Link href='/quotes' />} nativeButton={false} variant='ghost' className='w-fit px-0'>
          ← Quotations
        </Button>
        <Alert variant='destructive'>
          <AlertTitle>Unable to load quotations.</AlertTitle>
          <AlertDescription className='flex flex-col gap-3'>
            <span>{error ?? 'Please try again.'}</span>
            <Button type='button' variant='outline' className='w-fit' onClick={retry}>
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      </div>
    )
  }

  return (
    <div className='flex flex-col gap-6'>
      <div className='flex flex-wrap items-start justify-between gap-3'>
        <div>
          <Button render={<Link href='/quotes' />} nativeButton={false} variant='ghost' className='mb-2 w-fit px-0'>
            ← Quotations
          </Button>
          <h1 className='text-2xl font-semibold'>{quote.quote_number}</h1>
          <p className='text-muted-foreground text-sm'>{quote.case.title}</p>
        </div>
        <Badge variant='outline' className={cn(statusClass(quote.status))}>
          {quote.status_label}
        </Badge>
      </div>

      <section className='bg-card rounded-xl border p-5'>
        <dl className='grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-3'>
          <div>
            <dt className='text-muted-foreground'>Case</dt>
            <dd className='font-medium'>
              <Link href={`/opportunities/${quote.case.id}`} className='hover:underline'>
                {quote.case.case_number}
              </Link>
            </dd>
          </div>
          <div>
            <dt className='text-muted-foreground'>Customer</dt>
            <dd className='font-medium'>
              <button
                type='button'
                className='hover:underline'
                onClick={() =>
                  setCustomer({
                    id: quote.customer.id,
                    name: quote.customer.name,
                    email: quote.customer.email,
                    phone: quote.customer.phone,
                    status: 'lead',
                    sources: [],
                    properties: quote.property ? [quote.property] : [],
                    last_contact_at: null,
                    reply_channels: []
                  })
                }
              >
                {quote.customer.name}
              </button>
            </dd>
          </div>
          <div>
            <dt className='text-muted-foreground'>Property</dt>
            <dd className='font-medium'>{quote.property?.name ?? '—'}</dd>
          </div>
          <div>
            <dt className='text-muted-foreground'>Staff</dt>
            <dd className='font-medium'>{quote.staff?.display_name || quote.staff?.name || 'Unassigned'}</dd>
          </div>
          <div>
            <dt className='text-muted-foreground'>Amount</dt>
            <dd className='font-medium'>{quote.amount_label || '—'}</dd>
          </div>
          <div>
            <dt className='text-muted-foreground'>Currency</dt>
            <dd className='font-medium'>{quote.currency}</dd>
          </div>
          <div>
            <dt className='text-muted-foreground'>Created</dt>
            <dd className='font-medium'>{formatRelativeTime(quote.created_at) || '—'}</dd>
          </div>
          <div>
            <dt className='text-muted-foreground'>Valid Until</dt>
            <dd className={cn('font-medium', quote.is_expired && 'text-destructive')}>{formatDueAt(quote.valid_until) || '—'}</dd>
          </div>
          <div>
            <dt className='text-muted-foreground'>Updated</dt>
            <dd className='font-medium'>{formatRelativeTime(quote.updated_at) || '—'}</dd>
          </div>
        </dl>
        {quote.notes && (
          <div className='mt-4'>
            <p className='text-muted-foreground text-sm'>Notes</p>
            <p className='text-sm whitespace-pre-wrap'>{quote.notes}</p>
          </div>
        )}
      </section>

      <section className='bg-card rounded-xl border p-5'>
        <h2 className='mb-3 text-sm font-semibold tracking-wide uppercase'>Payments</h2>
        {payments.length === 0 ? (
          <p className='text-muted-foreground text-sm'>No payments are linked to this case yet.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Payment</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Amount</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {payments.map(item => (
                <TableRow key={item.id}>
                  <TableCell className='font-medium'>{item.payment_number}</TableCell>
                  <TableCell>{item.payment_type_label}</TableCell>
                  <TableCell>{item.amount_label}</TableCell>
                  <TableCell>{item.status_label}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>

      <CustomerDetailSheet
        customer={customer}
        onOpenChange={open => {
          if (!open) setCustomer(null)
        }}
      />
    </div>
  )
}

export default QuoteDetailView
