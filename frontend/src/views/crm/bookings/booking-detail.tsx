'use client'

import { useEffect, useState } from 'react'

import Link from 'next/link'
import { useParams } from 'next/navigation'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { isApiError } from '@/lib/api'
import { bookingsApi } from '@/lib/bookings/api'
import type { Booking } from '@/lib/bookings/types'
import type { Customer } from '@/lib/customers/types'
import { formatDueAt, formatRelativeTime } from '@/lib/datetime'
import { paymentsApi } from '@/lib/payments/api'
import type { Payment } from '@/lib/payments/types'
import { quotesApi } from '@/lib/quotes/api'
import type { Quote } from '@/lib/quotes/types'
import { cn } from '@/lib/utils'
import CustomerDetailSheet from '@/views/crm/customers/customer-detail-sheet'

const statusClass = (status: string) => {
  if (status === 'cancelled') return 'text-destructive'
  if (status === 'in_house') return 'border-transparent bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
  if (status === 'completed') return 'text-muted-foreground'
  if (status === 'upcoming') return 'border-transparent bg-sky-500/10 text-sky-700 dark:text-sky-400'

  return ''
}

const BookingDetailView = () => {
  const params = useParams<{ id: string }>()
  const bookingId = Number(params.id)
  const validId = Number.isInteger(bookingId) && bookingId > 0
  const [booking, setBooking] = useState<Booking | null>(null)
  const [quotes, setQuotes] = useState<Quote[]>([])
  const [payments, setPayments] = useState<Payment[]>([])
  const [loading, setLoading] = useState(validId)
  const [error, setError] = useState<string | null>(validId ? null : 'Booking not found.')
  const [customer, setCustomer] = useState<Customer | null>(null)

  const loadBooking = () =>
    bookingsApi.get(bookingId).then(async payload => {
      setBooking(payload)
      setError(null)

      try {
        const [quoteList, paymentList] = await Promise.all([
          quotesApi.list({ case: payload.case.id, page_size: 50, status: 'all' }),
          paymentsApi.list({ case: payload.case.id, page_size: 50, status: 'all' })
        ])

        setQuotes(quoteList.results)
        setPayments(paymentList.results)
      } catch {
        setQuotes([])
        setPayments([])
      }

      return payload
    })

  useEffect(() => {
    if (!validId) return

    let mounted = true

    loadBooking()
      .catch(err => {
        if (!mounted) return

        setBooking(null)
        setError(isApiError(err) ? err.message : 'Unable to load this booking.')
      })
      .finally(() => {
        if (!mounted) return

        setLoading(false)
      })

    return () => {
      mounted = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bookingId, validId])

  const retry = () => {
    setLoading(true)
    void loadBooking()
      .catch(err => {
        setBooking(null)
        setError(isApiError(err) ? err.message : 'Unable to load this booking.')
      })
      .finally(() => setLoading(false))
  }

  if (loading) {
    return <p className='text-muted-foreground text-sm'>Loading booking…</p>
  }

  if (error || !booking) {
    return (
      <div className='flex flex-col gap-4'>
        <Button render={<Link href='/bookings' />} nativeButton={false} variant='ghost' className='w-fit px-0'>
          ← Bookings
        </Button>
        <Alert variant='destructive'>
          <AlertTitle>Unable to load booking.</AlertTitle>
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
          <Button render={<Link href='/bookings' />} nativeButton={false} variant='ghost' className='mb-2 w-fit px-0'>
            ← Bookings
          </Button>
          <h1 className='text-2xl font-semibold'>{booking.booking_number}</h1>
          <p className='text-muted-foreground text-sm'>{booking.title}</p>
        </div>
        <Badge variant='outline' className={cn(statusClass(booking.status))}>
          {booking.status_label}
        </Badge>
      </div>

      <section className='bg-card rounded-xl border p-5'>
        <dl className='grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-3'>
          <div>
            <dt className='text-muted-foreground'>Case</dt>
            <dd className='font-medium'>
              <Link href={`/opportunities/${booking.case.id}`} className='hover:underline'>
                {booking.case.case_number}
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
                    id: booking.customer.id,
                    name: booking.customer.name,
                    email: booking.customer.email,
                    phone: booking.customer.phone,
                    status: 'lead',
                    sources: [],
                    properties: booking.property ? [booking.property] : [],
                    last_contact_at: null,
                    reply_channels: []
                  })
                }
              >
                {booking.customer.name}
              </button>
            </dd>
          </div>
          <div>
            <dt className='text-muted-foreground'>Property</dt>
            <dd className='font-medium'>{booking.property?.name ?? '—'}</dd>
          </div>
          <div>
            <dt className='text-muted-foreground'>Location</dt>
            <dd className='font-medium'>{booking.location?.name ?? '—'}</dd>
          </div>
          <div>
            <dt className='text-muted-foreground'>Staff</dt>
            <dd className='font-medium'>{booking.staff?.display_name || booking.staff?.name || 'Unassigned'}</dd>
          </div>
          <div>
            <dt className='text-muted-foreground'>Check-in</dt>
            <dd className='font-medium'>{booking.check_in ? formatDueAt(booking.check_in) : '—'}</dd>
          </div>
          <div>
            <dt className='text-muted-foreground'>Check-out</dt>
            <dd className='font-medium'>{booking.check_out ? formatDueAt(booking.check_out) : '—'}</dd>
          </div>
          <div>
            <dt className='text-muted-foreground'>Nights</dt>
            <dd className='font-medium'>{booking.nights ?? '—'}</dd>
          </div>
          <div>
            <dt className='text-muted-foreground'>Value</dt>
            <dd className='font-medium'>{booking.value_label || '—'}</dd>
          </div>
          <div>
            <dt className='text-muted-foreground'>Stage</dt>
            <dd className='font-medium'>{booking.stage_label}</dd>
          </div>
          <div>
            <dt className='text-muted-foreground'>Created</dt>
            <dd className='font-medium'>{formatRelativeTime(booking.created_at) || '—'}</dd>
          </div>
          <div>
            <dt className='text-muted-foreground'>Updated</dt>
            <dd className='font-medium'>{formatRelativeTime(booking.updated_at) || '—'}</dd>
          </div>
        </dl>
        {booking.notes && (
          <div className='mt-4'>
            <p className='text-muted-foreground text-sm'>Notes</p>
            <p className='text-sm whitespace-pre-wrap'>{booking.notes}</p>
          </div>
        )}
        {booking.request && (
          <div className='mt-4'>
            <p className='text-muted-foreground text-sm'>Request</p>
            <p className='text-sm whitespace-pre-wrap'>{booking.request}</p>
          </div>
        )}
      </section>

      <section className='bg-card rounded-xl border p-5'>
        <h2 className='mb-3 text-sm font-semibold tracking-wide uppercase'>Quotations</h2>
        {quotes.length === 0 ? (
          <p className='text-muted-foreground text-sm'>No quotations are linked to this booking yet.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Quotation</TableHead>
                <TableHead>Amount</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {quotes.map(item => (
                <TableRow key={item.id}>
                  <TableCell className='font-medium'>
                    <Link href={`/quotes/${item.id}`} className='hover:underline'>
                      {item.quote_number}
                    </Link>
                  </TableCell>
                  <TableCell>{item.amount_label || '—'}</TableCell>
                  <TableCell>{item.status_label}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>

      <section className='bg-card rounded-xl border p-5'>
        <h2 className='mb-3 text-sm font-semibold tracking-wide uppercase'>Payments</h2>
        {payments.length === 0 ? (
          <p className='text-muted-foreground text-sm'>No payments are linked to this booking yet.</p>
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

export default BookingDetailView
