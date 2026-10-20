'use client'

import { useCallback, useEffect, useState } from 'react'

import Link from 'next/link'

import { Badge } from '@/components/ui/badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { isApiError } from '@/lib/api'
import { availabilityApi } from '@/lib/availability/api'
import { formatDueAt } from '@/lib/datetime'
import { occupancyBadgeClass, statusBadgeClass } from '@/lib/locations/badges'
import type { Location } from '@/lib/locations/types'
import { cn } from '@/lib/utils'
import { paymentsApi } from '@/lib/payments/api'
import type { Payment } from '@/lib/payments/types'
import { casesApi } from '@/lib/pipeline/api'
import type { Opportunity } from '@/lib/pipeline/types'
import { quotesApi } from '@/lib/quotes/api'
import type { Quote } from '@/lib/quotes/types'

const EmptyState = ({ children }: { children: string }) => (
  <p className='text-muted-foreground text-sm'>{children}</p>
)

const LoadingState = ({ children }: { children: string }) => (
  <p className='text-muted-foreground text-sm'>{children}</p>
)

const ErrorState = ({ error }: { error: string }) => <p className='text-destructive text-sm'>{error}</p>

const usePropertyQuery = <T,>(loader: () => Promise<T[]>) => {
  const [items, setItems] = useState<T[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let mounted = true

    loader()
      .then(results => {
        if (!mounted) return
        setItems(results)
        setError(null)
      })
      .catch(err => {
        if (!mounted) return
        setItems([])
        setError(isApiError(err) ? err.message : 'Unable to load this section.')
      })
      .finally(() => {
        if (!mounted) return
        setLoading(false)
      })

    return () => {
      mounted = false
    }
  }, [loader])

  return { items, loading, error }
}

type SectionProps = {
  propertyId: number
}

export const PropertyAvailabilitySection = ({ propertyId }: SectionProps) => {
  const loader = useCallback(
    () => availabilityApi.list({ property: propertyId, page_size: 200 }).then(payload => payload.results),
    [propertyId]
  )

  const { items, loading, error } = usePropertyQuery<Location>(loader)

  if (loading) return <LoadingState>Loading availability…</LoadingState>
  if (error) return <ErrorState error={error} />
  if (items.length === 0) return <EmptyState>No locations are configured for availability on this property.</EmptyState>

  return (
    <div className='overflow-x-auto'>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Location</TableHead>
            <TableHead>Type</TableHead>
            <TableHead>Occupancy</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Current / next guest</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map(item => {
            const guest = item.current_booking || item.upcoming_booking

            return (
            <TableRow key={item.id}>
              <TableCell className='font-medium'>
                <Link href={`/properties/${propertyId}/locations/${item.id}`} className='hover:underline'>
                  {item.name}
                </Link>
              </TableCell>
              <TableCell>{item.type_label}</TableCell>
              <TableCell>
                <Badge variant='outline' className={cn(occupancyBadgeClass(item.occupancy))}>
                  {item.occupancy_label || item.occupancy || '—'}
                </Badge>
              </TableCell>
              <TableCell>
                <Badge variant='outline' className={cn(statusBadgeClass(item.status))}>
                  {item.status_label}
                </Badge>
              </TableCell>
              <TableCell>{guest?.customer.name ?? '—'}</TableCell>
            </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}

export const PropertyBookingsSection = ({ propertyId }: SectionProps) => {
  const loader = useCallback(
    () => casesApi.list({ property: propertyId, has_stay: true, page_size: 25 }).then(payload => payload.results),
    [propertyId]
  )

  const { items, loading, error } = usePropertyQuery<Opportunity>(loader)

  if (loading) return <LoadingState>Loading bookings…</LoadingState>
  if (error) return <ErrorState error={error} />
  if (items.length === 0) return <EmptyState>No bookings found for this property.</EmptyState>

  return (
    <div className='overflow-x-auto'>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Booking</TableHead>
            <TableHead>Customer</TableHead>
            <TableHead>Location</TableHead>
            <TableHead>Check-in</TableHead>
            <TableHead>Check-out</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map(item => (
            <TableRow key={item.id}>
              <TableCell className='font-medium'>
                <Link href={`/bookings/${item.id}`} className='hover:underline'>
                  {item.case_number}
                </Link>
              </TableCell>
              <TableCell>{item.customer.name}</TableCell>
              <TableCell>{item.location?.name ?? '—'}</TableCell>
              <TableCell>{item.check_in ? formatDueAt(item.check_in) : '—'}</TableCell>
              <TableCell>{item.check_out ? formatDueAt(item.check_out) : '—'}</TableCell>
              <TableCell>{item.stage_label}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

export const PropertyQuotesSection = ({ propertyId }: SectionProps) => {
  const loader = useCallback(
    () => quotesApi.list({ property: propertyId, page_size: 25 }).then(payload => payload.results),
    [propertyId]
  )

  const { items, loading, error } = usePropertyQuery<Quote>(loader)

  if (loading) return <LoadingState>Loading quotations…</LoadingState>
  if (error) return <ErrorState error={error} />
  if (items.length === 0) return <EmptyState>No quotations found for this property.</EmptyState>

  return (
    <div className='overflow-x-auto'>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Quote</TableHead>
            <TableHead>Case</TableHead>
            <TableHead>Customer</TableHead>
            <TableHead>Amount</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map(item => (
            <TableRow key={item.id}>
              <TableCell className='font-medium'>
                <Link href={`/quotes/${item.id}`} className='hover:underline'>
                  {item.quote_number}
                </Link>
              </TableCell>
              <TableCell>
                <Link href={`/cases/${item.case.id}`} className='hover:underline'>
                  {item.case.case_number}
                </Link>
              </TableCell>
              <TableCell>{item.customer.name}</TableCell>
              <TableCell>{item.amount_label ?? item.amount ?? '—'}</TableCell>
              <TableCell>{item.status_label}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

export const PropertyCasesSection = ({ propertyId }: SectionProps) => {
  const loader = useCallback(
    () => casesApi.list({ property: propertyId, page_size: 25 }).then(payload => payload.results),
    [propertyId]
  )

  const { items, loading, error } = usePropertyQuery<Opportunity>(loader)

  if (loading) return <LoadingState>Loading cases…</LoadingState>
  if (error) return <ErrorState error={error} />
  if (items.length === 0) return <EmptyState>No cases found for this property.</EmptyState>

  return (
    <div className='overflow-x-auto'>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Case</TableHead>
            <TableHead>Customer</TableHead>
            <TableHead>Location</TableHead>
            <TableHead>Stage</TableHead>
            <TableHead>Staff</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map(item => (
            <TableRow key={item.id}>
              <TableCell className='font-medium'>
                <Link href={`/cases/${item.id}`} className='hover:underline'>
                  {item.case_number}
                </Link>
              </TableCell>
              <TableCell>{item.customer.name}</TableCell>
              <TableCell>{item.location?.name ?? '—'}</TableCell>
              <TableCell>{item.stage_label}</TableCell>
              <TableCell>{item.assigned_to?.display_name ?? 'Unassigned'}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

export const PropertyPaymentsSection = ({ propertyId }: SectionProps) => {
  const loader = useCallback(
    () => paymentsApi.list({ property: propertyId, page_size: 25, status: 'all' }).then(payload => payload.results),
    [propertyId]
  )

  const { items, loading, error } = usePropertyQuery<Payment>(loader)

  if (loading) return <LoadingState>Loading payments…</LoadingState>
  if (error) return <ErrorState error={error} />
  if (items.length === 0) return <EmptyState>No payments found for this property.</EmptyState>

  return (
    <div className='overflow-x-auto'>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Payment</TableHead>
            <TableHead>Customer</TableHead>
            <TableHead>Case</TableHead>
            <TableHead>Amount</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map(item => (
            <TableRow key={item.id}>
              <TableCell className='font-medium'>
                <Link href='/payments' className='hover:underline'>
                  {item.payment_number}
                </Link>
              </TableCell>
              <TableCell>{item.customer.name}</TableCell>
              <TableCell>
                <Link href={`/cases/${item.case.id}`} className='hover:underline'>
                  {item.case.case_number}
                </Link>
              </TableCell>
              <TableCell>{item.amount_label ?? item.amount}</TableCell>
              <TableCell>{item.status_label}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
