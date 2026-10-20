'use client'

import { useEffect, useState, type ReactNode } from 'react'

import Link from 'next/link'
import { parseAsString, useQueryState } from 'nuqs'
import {
  ArrowRightIcon,
  BedDoubleIcon,
  CalendarArrowDownIcon,
  CalendarArrowUpIcon,
  ClipboardListIcon,
  CreditCardIcon,
  TargetIcon,
  UsersIcon,
  WrenchIcon
} from 'lucide-react'

import { useListPropertyQuery } from '@/components/properties/property-provider'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress, ProgressLabel, ProgressValue } from '@/components/ui/progress'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { isApiError } from '@/lib/api'
import type { Booking } from '@/lib/bookings/types'
import { dashboardApi } from '@/lib/dashboard/api'
import type { DashboardPayment, DashboardResponse, DashboardRoom } from '@/lib/dashboard/types'
import { formatDueAt, formatDueLabel } from '@/lib/datetime'
import { occupancyBadgeClass, statusBadgeClass } from '@/lib/locations/badges'
import type { CaseFollowUp } from '@/lib/pipeline/types'
import { cn } from '@/lib/utils'

const queryOptions = { history: 'replace' as const, clearOnDefault: true }

const bookingStatusClass = (status: string) => {
  if (status === 'cancelled') return 'text-destructive'
  if (status === 'in_house') return 'border-transparent bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
  if (status === 'completed') return 'text-muted-foreground'
  if (status === 'upcoming') return 'border-transparent bg-sky-500/10 text-sky-700 dark:text-sky-400'

  return ''
}

const paymentStatusClass = (status: string, overdue?: boolean) => {
  if (overdue || status === 'overdue') return 'text-destructive'
  if (status === 'pending' || status === 'proof_submitted' || status === 'pending_approval') {
    return 'border-transparent bg-amber-500/10 text-amber-800 dark:text-amber-400'
  }

  return ''
}

const followUpStatusClass = (status: string) => {
  if (status === 'overdue') return 'text-destructive'
  if (status === 'pending') return 'border-transparent bg-sky-500/10 text-sky-700 dark:text-sky-400'

  return ''
}

const KpiCard = ({
  icon,
  label,
  value,
  hint,
  href
}: {
  icon: ReactNode
  label: string
  value: string
  hint?: string
  href?: string
}) => {
  const body = (
    <Card className={cn(href && 'transition-colors hover:bg-muted/40')}>
      <CardHeader className='flex flex-row items-center justify-between gap-3 space-y-0 pb-2'>
        <CardTitle className='text-muted-foreground text-sm font-medium'>{label}</CardTitle>
        <div className='bg-primary/10 text-primary flex size-8 shrink-0 items-center justify-center rounded-sm'>
          {icon}
        </div>
      </CardHeader>
      <CardContent>
        <p className='text-2xl font-semibold tracking-tight'>{value}</p>
        {hint ? <p className='text-muted-foreground mt-1 text-sm'>{hint}</p> : null}
      </CardContent>
    </Card>
  )

  return href ? (
    <Link href={href} className='min-w-0'>
      {body}
    </Link>
  ) : (
    body
  )
}

const EmptyRow = ({ colSpan, message }: { colSpan: number; message: string }) => (
  <TableRow>
    <TableCell colSpan={colSpan} className='text-muted-foreground py-8 text-center'>
      {message}
    </TableCell>
  </TableRow>
)

const StayRow = ({ booking }: { booking: Booking }) => (
  <TableRow>
    <TableCell>
      <Link href={`/bookings/${booking.id}`} className='font-medium hover:underline'>
        {booking.booking_number}
      </Link>
      <p className='text-muted-foreground text-xs'>{booking.title}</p>
    </TableCell>
    <TableCell>
      <p>{booking.customer.name}</p>
      <p className='text-muted-foreground text-xs'>{booking.location?.name || booking.property?.name || 'Unassigned'}</p>
    </TableCell>
    <TableCell className='whitespace-nowrap'>{formatDueAt(booking.check_in) || '—'}</TableCell>
    <TableCell className='whitespace-nowrap'>{formatDueAt(booking.check_out) || '—'}</TableCell>
    <TableCell>
      <Badge variant='outline' className={bookingStatusClass(booking.status)}>
        {booking.status_label}
      </Badge>
    </TableCell>
  </TableRow>
)

const StayTable = ({
  title,
  description,
  href,
  bookings,
  empty
}: {
  title: string
  description: string
  href: string
  bookings: Booking[]
  empty: string
}) => (
  <Card>
    <CardHeader className='flex flex-row items-start justify-between gap-3'>
      <div>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </div>
      <Button variant='ghost' size='sm' render={<Link href={href} />} nativeButton={false}>
        View all
        <ArrowRightIcon />
      </Button>
    </CardHeader>
    <CardContent className='px-0'>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Booking</TableHead>
            <TableHead>Guest / room</TableHead>
            <TableHead>Check-in</TableHead>
            <TableHead>Check-out</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {bookings.length === 0 ? (
            <EmptyRow colSpan={5} message={empty} />
          ) : (
            bookings.map(booking => <StayRow key={booking.id} booking={booking} />)
          )}
        </TableBody>
      </Table>
    </CardContent>
  </Card>
)

const DashboardPageView = () => {
  const [property, setProperty] = useQueryState('property', parseAsString.withDefault('all').withOptions(queryOptions))
  const scopedProperty = useListPropertyQuery(property)
  const [data, setData] = useState<DashboardResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let mounted = true

    setLoading(true)
    dashboardApi
      .get({ property: scopedProperty })
      .then(payload => {
        if (!mounted) return
        setData(payload)
        setError(null)
      })
      .catch(err => {
        if (!mounted) return
        setError(isApiError(err) ? err.message : 'Unable to load the dashboard.')
        setData(null)
      })
      .finally(() => {
        if (!mounted) return
        setLoading(false)
      })

    return () => {
      mounted = false
    }
  }, [property, scopedProperty])

  const kpis = data?.kpis
  const occupancyHint =
    kpis == null ? undefined : `${kpis.occupied_rooms} of ${kpis.bookable_rooms} bookable rooms occupied`
  const pipelineMax = Math.max(1, ...(data?.pipeline.by_stage.map(stage => stage.count) ?? [1]))
  const roomMax = Math.max(1, ...(data?.rooms.by_status.map(status => status.count) ?? [1]))

  return (
    <div className='flex flex-col gap-6'>
      <div className='flex flex-wrap items-end justify-between gap-3'>
        <div>
          <h1 className='text-2xl font-semibold'>Dashboard</h1>
          <p className='text-muted-foreground text-sm'>
            Today&apos;s hotel operations: arrivals, occupancy, pipeline, and outstanding work from the live database.
          </p>
        </div>
        <div className='flex min-w-56 items-center gap-2'>
          <Select value={property} onValueChange={value => setProperty(value === 'all' ? null : value)}>
            <SelectTrigger className='w-full min-w-56'>
              <SelectValue placeholder='All properties' />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value='all'>All properties</SelectItem>
              {(data?.properties ?? []).map(item => (
                <SelectItem key={item.id} value={String(item.id)}>
                  {item.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {error ? (
        <Alert variant='destructive'>
          <AlertTitle>Dashboard unavailable</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      <div className='grid gap-4 sm:grid-cols-2 xl:grid-cols-4'>
        <KpiCard
          icon={<CalendarArrowDownIcon className='size-4' />}
          label='Check-ins today'
          value={loading ? '—' : String(kpis?.check_ins_today ?? 0)}
          hint={loading ? 'Loading live arrivals' : 'Arrivals scheduled for today'}
          href='/bookings?date_field=check_in&due=today'
        />
        <KpiCard
          icon={<CalendarArrowUpIcon className='size-4' />}
          label='Check-outs today'
          value={loading ? '—' : String(kpis?.check_outs_today ?? 0)}
          hint={loading ? 'Loading live departures' : 'Departures scheduled for today'}
          href='/bookings?date_field=check_out&due=today'
        />
        <KpiCard
          icon={<BedDoubleIcon className='size-4' />}
          label='In house'
          value={loading ? '—' : String(kpis?.in_house ?? 0)}
          hint={loading ? 'Loading occupancy' : occupancyHint}
          href='/bookings?status=in_house'
        />
        <KpiCard
          icon={<UsersIcon className='size-4' />}
          label='Occupancy'
          value={loading ? '—' : `${kpis?.occupancy_rate ?? 0}%`}
          hint={loading ? 'Loading rooms' : occupancyHint}
          href='/availability'
        />
      </div>

      <div className='grid gap-4 sm:grid-cols-2 xl:grid-cols-4'>
        <KpiCard
          icon={<TargetIcon className='size-4' />}
          label='Open pipeline'
          value={loading ? '—' : String(kpis?.open_pipeline ?? 0)}
          hint={kpis?.pipeline_value_label || 'No open enquiry value'}
          href='/opportunities'
        />
        <KpiCard
          icon={<CreditCardIcon className='size-4' />}
          label='Pending payments'
          value={loading ? '—' : String(kpis?.pending_payments ?? 0)}
          hint={
            kpis
              ? `${kpis.pending_amount_label || 'MYR 0'} outstanding${kpis.overdue_payments ? ` · ${kpis.overdue_payments} overdue` : ''}`
              : 'Loading payments'
          }
          href='/payments'
        />
        <KpiCard
          icon={<ClipboardListIcon className='size-4' />}
          label='Follow-ups'
          value={loading ? '—' : String(kpis?.open_follow_ups ?? 0)}
          hint={kpis ? `${kpis.overdue_follow_ups} overdue` : 'Loading follow-ups'}
          href='/follow-ups?status=actionable'
        />
        <KpiCard
          icon={<WrenchIcon className='size-4' />}
          label='Rooms needing attention'
          value={loading ? '—' : String(kpis?.rooms_attention ?? 0)}
          hint={kpis ? `${kpis.open_maintenance} open maintenance` : 'Loading rooms'}
          href='/availability'
        />
      </div>

      <div className='grid gap-6 xl:grid-cols-2'>
        <StayTable
          title='Arrivals today'
          description='Guests checking in today'
          href='/bookings?date_field=check_in&due=today'
          bookings={data?.arrivals ?? []}
          empty={loading ? 'Loading arrivals…' : 'No arrivals scheduled today.'}
        />
        <StayTable
          title='Departures today'
          description='Guests checking out today'
          href='/bookings?date_field=check_out&due=today'
          bookings={data?.departures ?? []}
          empty={loading ? 'Loading departures…' : 'No departures scheduled today.'}
        />
      </div>

      <div className='grid gap-6 xl:grid-cols-2'>
        <Card>
          <CardHeader className='flex flex-row items-start justify-between gap-3'>
            <div>
              <CardTitle>Room status</CardTitle>
              <CardDescription>
                {kpis?.revenue_this_month_label
                  ? `${data?.rooms.occupied ?? 0} occupied · revenue this month ${kpis.revenue_this_month_label}`
                  : 'Operational status of active rooms'}
              </CardDescription>
            </div>
            <Button variant='ghost' size='sm' render={<Link href='/availability' />} nativeButton={false}>
              Availability
              <ArrowRightIcon />
            </Button>
          </CardHeader>
          <CardContent className='space-y-4'>
            <Progress value={kpis?.occupancy_rate ?? 0} className='w-full'>
              <div className='flex w-full items-center'>
                <ProgressLabel>Occupancy</ProgressLabel>
                <ProgressValue />
              </div>
            </Progress>
            <div className='grid gap-3 sm:grid-cols-2'>
              {(data?.rooms.by_status ?? []).map(status => (
                <div key={status.id} className='flex items-center justify-between gap-3 rounded-md border px-3 py-2'>
                  <Badge variant='outline' className={statusBadgeClass(status.id)}>
                    {status.label}
                  </Badge>
                  <span className='text-sm font-medium'>{status.count}</span>
                  <span className='sr-only'>
                    {status.count} of {roomMax}
                  </span>
                </div>
              ))}
            </div>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Room</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Occupancy</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(data?.rooms.attention ?? []).length === 0 ? (
                  <EmptyRow colSpan={3} message={loading ? 'Loading rooms…' : 'No rooms need attention.'} />
                ) : (
                  (data?.rooms.attention ?? []).map((room: DashboardRoom) => (
                    <TableRow key={room.id}>
                      <TableCell>
                        <Link
                          href={room.property ? `/properties/${room.property.id}/locations/${room.id}` : '/availability'}
                          className='font-medium hover:underline'
                        >
                          {room.name}
                        </Link>
                        <p className='text-muted-foreground text-xs'>
                          {[room.code, room.property?.name].filter(Boolean).join(' · ') || room.type_label}
                        </p>
                      </TableCell>
                      <TableCell>
                        <Badge variant='outline' className={statusBadgeClass(room.status)}>
                          {room.status_label}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant='outline' className={occupancyBadgeClass(room.occupancy)}>
                          {room.occupancy_label}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className='flex flex-row items-start justify-between gap-3'>
            <div>
              <CardTitle>Pipeline</CardTitle>
              <CardDescription>
                {data?.pipeline.open_value_label
                  ? `${data.pipeline.open_count} open enquiries · ${data.pipeline.open_value_label}`
                  : 'Open sales cases by stage'}
              </CardDescription>
            </div>
            <Button variant='ghost' size='sm' render={<Link href='/opportunities' />} nativeButton={false}>
              Pipeline
              <ArrowRightIcon />
            </Button>
          </CardHeader>
          <CardContent className='space-y-3'>
            {(data?.pipeline.by_stage ?? []).map(stage => (
              <div key={stage.id} className='space-y-1.5'>
                <div className='flex items-center justify-between gap-3 text-sm'>
                  <span className='font-medium'>{stage.label}</span>
                  <span className='text-muted-foreground'>
                    {stage.count} · {stage.value_label || 'MYR 0'}
                  </span>
                </div>
                <div className='bg-muted h-1.5 overflow-hidden rounded-full'>
                  <div
                    className='bg-primary h-full rounded-full'
                    style={{ width: `${Math.round((stage.count / pipelineMax) * 100)}%` }}
                  />
                </div>
              </div>
            ))}
            {!data && loading ? <p className='text-muted-foreground text-sm'>Loading pipeline…</p> : null}
          </CardContent>
        </Card>
      </div>

      <div className='grid gap-6 xl:grid-cols-2'>
        <Card>
          <CardHeader className='flex flex-row items-start justify-between gap-3'>
            <div>
              <CardTitle>Pending payments</CardTitle>
              <CardDescription>Deposits and balances waiting for collection or approval</CardDescription>
            </div>
            <Button variant='ghost' size='sm' render={<Link href='/payments' />} nativeButton={false}>
              Payments
              <ArrowRightIcon />
            </Button>
          </CardHeader>
          <CardContent className='px-0'>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Payment</TableHead>
                  <TableHead>Guest</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(data?.pending_payments ?? []).length === 0 ? (
                  <EmptyRow colSpan={4} message={loading ? 'Loading payments…' : 'No pending payments.'} />
                ) : (
                  (data?.pending_payments ?? []).map((payment: DashboardPayment) => (
                    <TableRow key={payment.id}>
                      <TableCell>
                        <Link href={`/cases/${payment.case.id}`} className='font-medium hover:underline'>
                          {payment.payment_number}
                        </Link>
                        <p className='text-muted-foreground text-xs'>{payment.case.case_number}</p>
                      </TableCell>
                      <TableCell>
                        <p>{payment.customer.name}</p>
                        <p className='text-muted-foreground text-xs'>{payment.property?.name || '—'}</p>
                      </TableCell>
                      <TableCell className='whitespace-nowrap'>{payment.amount_label || payment.amount || '—'}</TableCell>
                      <TableCell>
                        <Badge variant='outline' className={paymentStatusClass(payment.status, payment.is_overdue)}>
                          {payment.status_label}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className='flex flex-row items-start justify-between gap-3'>
            <div>
              <CardTitle>Open follow-ups</CardTitle>
              <CardDescription>Staff tasks that still need action</CardDescription>
            </div>
            <Button variant='ghost' size='sm' render={<Link href='/follow-ups?status=actionable' />} nativeButton={false}>
              Follow-ups
              <ArrowRightIcon />
            </Button>
          </CardHeader>
          <CardContent className='px-0'>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Task</TableHead>
                  <TableHead>Guest</TableHead>
                  <TableHead>Due</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(data?.follow_ups ?? []).length === 0 ? (
                  <EmptyRow colSpan={4} message={loading ? 'Loading follow-ups…' : 'No open follow-ups.'} />
                ) : (
                  (data?.follow_ups ?? []).map((item: CaseFollowUp) => (
                    <TableRow key={item.id}>
                      <TableCell>
                        <Link href={`/follow-ups`} className='font-medium hover:underline'>
                          {item.title}
                        </Link>
                        <p className='text-muted-foreground text-xs'>{item.case?.case_number || item.type_label}</p>
                      </TableCell>
                      <TableCell>{item.customer?.name || '—'}</TableCell>
                      <TableCell className='whitespace-nowrap'>{formatDueLabel(item.due_at, new Date(), item.status)}</TableCell>
                      <TableCell>
                        <Badge variant='outline' className={followUpStatusClass(item.status)}>
                          {item.status_label}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className='flex flex-row items-start justify-between gap-3'>
          <div>
            <CardTitle>Recent bookings</CardTitle>
            <CardDescription>Latest reservations created in the CRM</CardDescription>
          </div>
          <Button variant='ghost' size='sm' render={<Link href='/bookings' />} nativeButton={false}>
            Bookings
            <ArrowRightIcon />
          </Button>
        </CardHeader>
        <CardContent className='px-0'>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Booking</TableHead>
                <TableHead>Guest</TableHead>
                <TableHead>Property / room</TableHead>
                <TableHead>Stay</TableHead>
                <TableHead>Value</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(data?.recent_bookings ?? []).length === 0 ? (
                <EmptyRow colSpan={6} message={loading ? 'Loading bookings…' : 'No bookings yet.'} />
              ) : (
                (data?.recent_bookings ?? []).map(booking => (
                  <TableRow key={booking.id}>
                    <TableCell>
                      <Link href={`/bookings/${booking.id}`} className='font-medium hover:underline'>
                        {booking.booking_number}
                      </Link>
                      <p className='text-muted-foreground text-xs'>{booking.title}</p>
                    </TableCell>
                    <TableCell>{booking.customer.name}</TableCell>
                    <TableCell>
                      <p>{booking.property?.name || '—'}</p>
                      <p className='text-muted-foreground text-xs'>{booking.location?.name || 'Unassigned room'}</p>
                    </TableCell>
                    <TableCell className='whitespace-nowrap'>
                      {formatDueAt(booking.check_in) || '—'}
                      {booking.check_out ? ` → ${formatDueAt(booking.check_out)}` : ''}
                    </TableCell>
                    <TableCell className='whitespace-nowrap'>{booking.value_label || booking.value || '—'}</TableCell>
                    <TableCell>
                      <Badge variant='outline' className={bookingStatusClass(booking.status)}>
                        {booking.status_label}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}

export default DashboardPageView
