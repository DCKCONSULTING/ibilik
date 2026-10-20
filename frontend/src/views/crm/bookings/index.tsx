'use client'

import { useEffect, useMemo, useState, type ReactNode } from 'react'

import Link from 'next/link'
import { parseAsInteger, parseAsString, useQueryState } from 'nuqs'
import { SearchIcon } from 'lucide-react'

import { useListPropertyQuery } from '@/components/properties/property-provider'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { InputGroup, InputGroupAddon, InputGroupInput } from '@/components/ui/input-group'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { isApiError } from '@/lib/api'
import { bookingsApi } from '@/lib/bookings/api'
import type { Booking, BookingListResponse } from '@/lib/bookings/types'
import { customersApi } from '@/lib/customers/api'
import type { Customer } from '@/lib/customers/types'
import { formatDueAt } from '@/lib/datetime'
import type { PipelineLocation, PipelineProperty, PipelineUser } from '@/lib/pipeline/types'
import { cn } from '@/lib/utils'
import CustomerDetailSheet from '@/views/crm/customers/customer-detail-sheet'

const STATUS_OPTIONS = [
  { id: 'all', label: 'All' },
  { id: 'upcoming', label: 'Upcoming' },
  { id: 'in_house', label: 'In house' },
  { id: 'completed', label: 'Completed' },
  { id: 'cancelled', label: 'Cancelled' }
]

const DUE_OPTIONS = [
  { id: 'all', label: 'All' },
  { id: 'today', label: 'Today' },
  { id: 'this_week', label: 'This Week' },
  { id: 'this_month', label: 'This Month' },
  { id: 'custom', label: 'Custom Range' }
]

const DATE_FIELD_OPTIONS = [
  { id: 'check_in', label: 'Check-in' },
  { id: 'check_out', label: 'Check-out' },
  { id: 'created_at', label: 'Created Date' }
]

const SORT_OPTIONS = [
  { id: 'check_in', label: 'Check-in (soonest)' },
  { id: '-check_in', label: 'Check-in (latest)' },
  { id: 'check_out', label: 'Check-out (soonest)' },
  { id: '-check_out', label: 'Check-out (latest)' },
  { id: '-created_at', label: 'Created (newest)' },
  { id: 'created_at', label: 'Created (oldest)' },
  { id: '-value', label: 'Value (high)' },
  { id: 'value', label: 'Value (low)' }
]

const queryOptions = { history: 'replace' as const, clearOnDefault: true }
const FILTER_FIELD_CLASS = 'grid min-w-0 grid-cols-[8rem_minmax(0,1fr)] items-center gap-2'

const FilterSelect = ({
  label,
  value,
  onValueChange,
  children
}: {
  label: string
  value: string
  onValueChange: (value: string | null) => void
  children: ReactNode
}) => (
  <div className={FILTER_FIELD_CLASS}>
    <FieldLabel className='text-muted-foreground'>{label}</FieldLabel>
    <div className='min-w-0'>
      <Select value={value} onValueChange={onValueChange}>
        <SelectTrigger className='w-full min-w-0'>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>{children}</SelectContent>
      </Select>
    </div>
  </div>
)

const statusBadgeClass = (status: string) => {
  if (status === 'cancelled') return 'text-destructive'
  if (status === 'in_house') return 'border-transparent bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
  if (status === 'completed') return 'text-muted-foreground'
  if (status === 'upcoming') return 'border-transparent bg-sky-500/10 text-sky-700 dark:text-sky-400'

  return ''
}

const BookingsPageView = () => {
  const [status, setStatus] = useQueryState('status', parseAsString.withDefault('all').withOptions(queryOptions))
  const [property, setProperty] = useQueryState('property', parseAsString.withDefault('all').withOptions(queryOptions))
  const scopedProperty = useListPropertyQuery(property)
  const [location, setLocation] = useQueryState('location', parseAsString.withDefault('all').withOptions(queryOptions))
  const [staff, setStaff] = useQueryState('staff', parseAsString.withDefault('all').withOptions(queryOptions))
  const [customer, setCustomerFilter] = useQueryState('customer', parseAsString.withDefault('all').withOptions(queryOptions))
  const [caseNumber, setCaseNumber] = useQueryState('case_number', parseAsString.withDefault('').withOptions(queryOptions))
  const [dateField, setDateField] = useQueryState('date_field', parseAsString.withDefault('check_in').withOptions(queryOptions))
  const [due, setDue] = useQueryState('due', parseAsString.withDefault('all').withOptions(queryOptions))
  const [dueFrom, setDueFrom] = useQueryState('date_from', parseAsString.withDefault('').withOptions(queryOptions))
  const [dueTo, setDueTo] = useQueryState('date_to', parseAsString.withDefault('').withOptions(queryOptions))
  const [search, setSearch] = useQueryState('search', parseAsString.withDefault('').withOptions(queryOptions))
  const [ordering, setOrdering] = useQueryState('ordering', parseAsString.withDefault('check_in').withOptions(queryOptions))
  const [page, setPage] = useQueryState('page', parseAsInteger.withDefault(1).withOptions(queryOptions))

  const [items, setItems] = useState<Booking[]>([])

  const [meta, setMeta] = useState<Pick<BookingListResponse, 'statuses' | 'staff' | 'properties' | 'locations'>>({
    statuses: [],
    staff: [],
    properties: [],
    locations: []
  })

  const [customers, setCustomers] = useState<Customer[]>([])
  const [count, setCount] = useState(0)
  const [pageSize, setPageSize] = useState(25)
  const [hasNext, setHasNext] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [customerSheet, setCustomerSheet] = useState<Customer | null>(null)

  const filtersActive = useMemo(
    () =>
      status !== 'all' ||
      property !== 'all' ||
      location !== 'all' ||
      staff !== 'all' ||
      customer !== 'all' ||
      due !== 'all' ||
      Boolean(caseNumber.trim()) ||
      Boolean(search.trim()),
    [caseNumber, customer, due, location, property, search, staff, status]
  )

  const load = () => {
    setLoading(true)

    return bookingsApi
      .list({
        status,
        property: scopedProperty,
        location: location !== 'all' ? location : undefined,
        staff: staff !== 'all' ? staff : undefined,
        customer: customer !== 'all' ? customer : undefined,
        case_number: caseNumber.trim() || undefined,
        date_field: dateField,
        due: due !== 'all' ? due : undefined,
        date_from: due === 'custom' && dueFrom ? dueFrom : undefined,
        date_to: due === 'custom' && dueTo ? dueTo : undefined,
        search: search.trim() || undefined,
        ordering,
        page,
        page_size: 25
      })
      .then(payload => {
        setItems(payload.results)
        setCount(payload.count)
        setPageSize(payload.page_size)
        setHasNext(payload.has_next)
        setMeta({
          statuses: payload.statuses,
          staff: payload.staff,
          properties: payload.properties,
          locations: payload.locations
        })
        setError(null)
      })
      .catch(err => {
        setItems([])
        setError(isApiError(err) ? err.message : 'Unable to load bookings.')
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    const handle = window.setTimeout(() => {
      void load()
    }, 250)

    return () => window.clearTimeout(handle)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, property, location, staff, customer, caseNumber, dateField, due, dueFrom, dueTo, search, ordering, page])

  useEffect(() => {
    customersApi
      .list({ page_size: 100 })
      .then(payload => setCustomers(payload.results))
      .catch(() => setCustomers([]))
  }, [])

  const clearFilters = () => {
    void setStatus('all')
    void setProperty('all')
    void setLocation('all')
    void setStaff('all')
    void setCustomerFilter('all')
    void setCaseNumber('')
    void setDateField('check_in')
    void setDue('all')
    void setDueFrom('')
    void setDueTo('')
    void setSearch('')
    void setOrdering('check_in')
    void setPage(1)
  }

  const changeFilter = (setter: (value: string) => unknown, value: string | null) => {
    if (!value) return
    void setter(value)
    void setPage(1)
  }

  const customerFromBooking = (item: Booking): Customer => ({
    id: item.customer.id,
    name: item.customer.name,
    email: item.customer.email,
    phone: item.customer.phone,
    status: 'lead',
    sources: [],
    properties: item.property ? [item.property] : [],
    last_contact_at: null,
    reply_channels: []
  })

  const start = count === 0 ? 0 : (page - 1) * pageSize + 1
  const end = Math.min(page * pageSize, count)
  const statusOptions = meta.statuses.length > 0 ? [{ id: 'all', label: 'All' }, ...meta.statuses] : STATUS_OPTIONS

  return (
    <div className='flex flex-col gap-6'>
      <div>
        <h1 className='text-2xl font-semibold'>Bookings</h1>
        <p className='text-muted-foreground text-sm'>Confirmed reservations and stay records across properties.</p>
      </div>

      {error && (
        <Alert variant='destructive'>
          <AlertTitle>Unable to load bookings.</AlertTitle>
          <AlertDescription className='flex flex-col gap-3'>
            <span>Please try again.</span>
            <Button type='button' variant='outline' className='w-fit' onClick={() => void load()}>
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      )}

      <Card className='shadow-none'>
        <CardHeader className='gap-4'>
          <div className='flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between'>
            <div>
              <CardTitle>Bookings</CardTitle>
              <CardDescription>Filter stays by status, property, dates, and guest.</CardDescription>
            </div>
            <InputGroup className='lg:max-w-80'>
              <InputGroupAddon>
                <SearchIcon className='size-4' />
              </InputGroupAddon>
              <InputGroupInput
                type='search'
                placeholder='Search bookings...'
                value={search}
                onChange={event => {
                  void setSearch(event.target.value)
                  void setPage(1)
                }}
              />
            </InputGroup>
          </div>
          <div className='grid gap-3 sm:grid-cols-2 xl:grid-cols-4'>
            <FilterSelect label='Status' value={status} onValueChange={value => changeFilter(setStatus, value)}>
              {statusOptions.map(item => (
                <SelectItem key={item.id} value={item.id}>
                  {item.label}
                </SelectItem>
              ))}
            </FilterSelect>
            <FilterSelect label='Property' value={property} onValueChange={value => changeFilter(setProperty, value)}>
              <SelectItem value='all'>All Properties</SelectItem>
              {meta.properties.map((item: PipelineProperty) => (
                <SelectItem key={item.id} value={String(item.id)}>
                  {item.name}
                </SelectItem>
              ))}
            </FilterSelect>
            <FilterSelect label='Location' value={location} onValueChange={value => changeFilter(setLocation, value)}>
              <SelectItem value='all'>All Locations</SelectItem>
              {meta.locations.map((item: PipelineLocation) => (
                <SelectItem key={item.id} value={String(item.id)}>
                  {item.name}
                </SelectItem>
              ))}
            </FilterSelect>
            <FilterSelect label='Staff' value={staff} onValueChange={value => changeFilter(setStaff, value)}>
              <SelectItem value='all'>All Staff</SelectItem>
              {meta.staff.map((user: PipelineUser) => (
                <SelectItem key={user.id} value={String(user.id)}>
                  {user.display_name || user.name || user.username}
                </SelectItem>
              ))}
            </FilterSelect>
            <FilterSelect label='Customer' value={customer} onValueChange={value => changeFilter(setCustomerFilter, value)}>
              <SelectItem value='all'>All Customers</SelectItem>
              {customers.map(item => (
                <SelectItem key={item.id} value={String(item.id)}>
                  {item.name}
                </SelectItem>
              ))}
            </FilterSelect>
            <div className={FILTER_FIELD_CLASS}>
              <FieldLabel className='text-muted-foreground'>Booking</FieldLabel>
              <Input
                className='w-full min-w-0'
                value={caseNumber}
                placeholder='CASE-1001'
                onChange={event => {
                  void setCaseNumber(event.target.value)
                  void setPage(1)
                }}
              />
            </div>
            <FilterSelect label='Date Field' value={dateField} onValueChange={value => changeFilter(setDateField, value)}>
              {DATE_FIELD_OPTIONS.map(item => (
                <SelectItem key={item.id} value={item.id}>
                  {item.label}
                </SelectItem>
              ))}
            </FilterSelect>
            <FilterSelect label='Date' value={due} onValueChange={value => changeFilter(setDue, value)}>
              {DUE_OPTIONS.map(item => (
                <SelectItem key={item.id} value={item.id}>
                  {item.label}
                </SelectItem>
              ))}
            </FilterSelect>
            <FilterSelect label='Sort' value={ordering} onValueChange={value => changeFilter(setOrdering, value)}>
              {SORT_OPTIONS.map(item => (
                <SelectItem key={item.id} value={item.id}>
                  {item.label}
                </SelectItem>
              ))}
            </FilterSelect>
            {due === 'custom' && (
              <>
                <div className={FILTER_FIELD_CLASS}>
                  <FieldLabel className='text-muted-foreground'>From</FieldLabel>
                  <Input type='date' className='w-full min-w-0' value={dueFrom} onChange={event => changeFilter(setDueFrom, event.target.value)} />
                </div>
                <div className={FILTER_FIELD_CLASS}>
                  <FieldLabel className='text-muted-foreground'>To</FieldLabel>
                  <Input type='date' className='w-full min-w-0' value={dueTo} onChange={event => changeFilter(setDueTo, event.target.value)} />
                </div>
              </>
            )}
          </div>
        </CardHeader>
        <CardContent className='overflow-x-auto'>
          {loading && <p className='text-muted-foreground text-sm'>Loading bookings…</p>}
          {!loading && error && <p className='text-muted-foreground text-sm'>Bookings could not be loaded.</p>}
          {!loading && !error && items.length === 0 && (
            <div className='flex flex-col gap-3'>
              <p className='text-muted-foreground text-sm'>{filtersActive ? 'No bookings match your filters.' : 'No bookings found'}</p>
              {filtersActive && (
                <Button type='button' variant='outline' className='w-fit' onClick={clearFilters}>
                  Clear Filters
                </Button>
              )}
            </div>
          )}
          {!loading && !error && items.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Booking</TableHead>
                  <TableHead>Customer</TableHead>
                  <TableHead>Property</TableHead>
                  <TableHead>Location</TableHead>
                  <TableHead>Check-in</TableHead>
                  <TableHead>Check-out</TableHead>
                  <TableHead>Nights</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Staff</TableHead>
                  <TableHead>Value</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map(item => (
                  <TableRow key={item.id}>
                    <TableCell className='font-medium'>
                      <Link href={`/bookings/${item.id}`} className='hover:underline'>
                        {item.booking_number}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <button type='button' className='hover:underline' onClick={() => setCustomerSheet(customerFromBooking(item))}>
                        {item.customer.name}
                      </button>
                    </TableCell>
                    <TableCell>{item.property?.name ?? '—'}</TableCell>
                    <TableCell>{item.location?.name ?? '—'}</TableCell>
                    <TableCell>{item.check_in ? formatDueAt(item.check_in) : '—'}</TableCell>
                    <TableCell>{item.check_out ? formatDueAt(item.check_out) : '—'}</TableCell>
                    <TableCell>{item.nights ?? '—'}</TableCell>
                    <TableCell>
                      <Badge variant='outline' className={cn(statusBadgeClass(item.status))}>
                        {item.status_label}
                      </Badge>
                    </TableCell>
                    <TableCell>{item.staff?.display_name || item.staff?.name || 'Unassigned'}</TableCell>
                    <TableCell>{item.value_label || '—'}</TableCell>
                    <TableCell>
                      <Button render={<Link href={`/bookings/${item.id}`} />} nativeButton={false} type='button' size='sm' variant='ghost'>
                        Open
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          {!loading && !error && count > 0 && (
            <div className='mt-4 flex flex-wrap items-center justify-between gap-2'>
              <p className='text-muted-foreground text-sm'>
                {start}–{end} of {count}
              </p>
              <div className='flex gap-2'>
                <Button variant='outline' size='sm' disabled={page === 1} onClick={() => void setPage(Math.max(1, page - 1))}>
                  Previous
                </Button>
                <Button variant='outline' size='sm' disabled={!hasNext} onClick={() => void setPage(page + 1)}>
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <CustomerDetailSheet
        customer={customerSheet}
        onOpenChange={open => {
          if (!open) setCustomerSheet(null)
        }}
      />
    </div>
  )
}

export default BookingsPageView
