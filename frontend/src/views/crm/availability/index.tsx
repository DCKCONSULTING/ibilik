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
import { InputGroup, InputGroupAddon, InputGroupInput } from '@/components/ui/input-group'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { isApiError } from '@/lib/api'
import { availabilityApi } from '@/lib/availability/api'
import type { AvailabilityListResponse } from '@/lib/availability/api'
import { formatDueAt } from '@/lib/datetime'
import { occupancyBadgeClass, statusBadgeClass } from '@/lib/locations/badges'
import { LOCATION_OCCUPANCIES, LOCATION_STATUSES, LOCATION_TYPES, type Location, type LocationOption, type LocationProperty } from '@/lib/locations/types'
import { cn } from '@/lib/utils'

const OCCUPANCY_OPTIONS = [{ id: 'all', label: 'All' }, ...LOCATION_OCCUPANCIES]

const ACTIVE_OPTIONS = [
  { id: 'true', label: 'Active' },
  { id: 'false', label: 'Inactive' },
  { id: 'all', label: 'All' }
]

const BOOKABLE_NOW_OPTIONS = [
  { id: 'true', label: 'Available for booking' },
  { id: 'false', label: 'Not available for booking' },
  { id: 'all', label: 'All' }
]

const YES_NO_OPTIONS = [
  { id: 'true', label: 'Yes' },
  { id: 'false', label: 'No' },
  { id: 'all', label: 'All' }
]

const SORT_OPTIONS = [
  { id: 'property', label: 'Property' },
  { id: 'name', label: 'Location A–Z' },
  { id: '-name', label: 'Location Z–A' },
  { id: 'type', label: 'Type' },
  { id: 'status', label: 'Status' },
  { id: 'floor', label: 'Floor' },
  { id: '-updated_at', label: 'Updated (newest)' }
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

const guestBooking = (item: Location) => item.current_booking || item.upcoming_booking || item.case || null

const AvailabilityPageView = () => {
  const [occupancy, setOccupancy] = useQueryState('occupancy', parseAsString.withDefault('all').withOptions(queryOptions))
  const [status, setStatus] = useQueryState('status', parseAsString.withDefault('all').withOptions(queryOptions))
  const [property, setProperty] = useQueryState('property', parseAsString.withDefault('all').withOptions(queryOptions))
  const scopedProperty = useListPropertyQuery(property)
  const [type, setType] = useQueryState('type', parseAsString.withDefault('all').withOptions(queryOptions))
  const [floor, setFloor] = useQueryState('floor', parseAsString.withDefault('all').withOptions(queryOptions))
  const [active, setActive] = useQueryState('active', parseAsString.withDefault('true').withOptions(queryOptions))
  const [bookableNow, setBookableNow] = useQueryState('bookable_now', parseAsString.withDefault('all').withOptions(queryOptions))
  const [maintenance, setMaintenance] = useQueryState('maintenance', parseAsString.withDefault('all').withOptions(queryOptions))
  const [checkInToday, setCheckInToday] = useQueryState('check_in_today', parseAsString.withDefault('all').withOptions(queryOptions))
  const [checkOutToday, setCheckOutToday] = useQueryState('check_out_today', parseAsString.withDefault('all').withOptions(queryOptions))
  const [guest, setGuest] = useQueryState('guest', parseAsString.withDefault('').withOptions(queryOptions))
  const [search, setSearch] = useQueryState('search', parseAsString.withDefault('').withOptions(queryOptions))
  const [ordering, setOrdering] = useQueryState('ordering', parseAsString.withDefault('property').withOptions(queryOptions))
  const [page, setPage] = useQueryState('page', parseAsInteger.withDefault(1).withOptions(queryOptions))

  const [items, setItems] = useState<Location[]>([])

  const [meta, setMeta] = useState<Pick<AvailabilityListResponse, 'types' | 'statuses' | 'occupancies' | 'properties' | 'floors'>>({
    types: [...LOCATION_TYPES],
    statuses: [...LOCATION_STATUSES],
    occupancies: OCCUPANCY_OPTIONS.filter(item => item.id !== 'all'),
    properties: [],
    floors: []
  })

  const [count, setCount] = useState(0)
  const [pageSize, setPageSize] = useState(50)
  const [hasNext, setHasNext] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const filtersActive = useMemo(
    () =>
      occupancy !== 'all' ||
      status !== 'all' ||
      property !== 'all' ||
      type !== 'all' ||
      floor !== 'all' ||
      active !== 'all' ||
      bookableNow !== 'all' ||
      maintenance !== 'all' ||
      checkInToday !== 'all' ||
      checkOutToday !== 'all' ||
      Boolean(guest.trim()) ||
      Boolean(search.trim()),
    [active, bookableNow, checkInToday, checkOutToday, floor, guest, maintenance, occupancy, property, search, status, type]
  )

  const load = () => {
    setLoading(true)

    return availabilityApi
      .list({
        occupancy,
        status: status !== 'all' ? status : undefined,
        property: scopedProperty,
        type: type !== 'all' ? type : undefined,
        floor: floor !== 'all' ? floor : undefined,
        active: active !== 'all' ? active : undefined,
        available_for_booking: bookableNow !== 'all' ? bookableNow : undefined,
        maintenance: maintenance !== 'all' ? maintenance : undefined,
        check_in_today: checkInToday !== 'all' ? checkInToday : undefined,
        check_out_today: checkOutToday !== 'all' ? checkOutToday : undefined,
        guest: guest.trim() || undefined,
        search: search.trim() || undefined,
        ordering,
        page,
        page_size: 50
      })
      .then(payload => {
        setItems(payload.results)
        setCount(payload.count)
        setPageSize(payload.page_size)
        setHasNext(payload.has_next)
        setMeta({
          types: payload.types?.length ? payload.types : [...LOCATION_TYPES],
          statuses: payload.statuses?.length ? payload.statuses : [...LOCATION_STATUSES],
          occupancies: payload.occupancies?.length ? payload.occupancies : OCCUPANCY_OPTIONS.filter(item => item.id !== 'all'),
          properties: payload.properties ?? [],
          floors: payload.floors ?? []
        })
        setError(null)
      })
      .catch(err => {
        setItems([])
        setError(isApiError(err) ? err.message : 'Unable to load availability.')
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    const handle = window.setTimeout(() => {
      void load()
    }, 250)

    return () => window.clearTimeout(handle)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [occupancy, status, property, type, floor, active, bookableNow, maintenance, checkInToday, checkOutToday, guest, search, ordering, page])

  const clearFilters = () => {
    void setOccupancy('all')
    void setStatus('all')
    void setProperty('all')
    void setType('all')
    void setFloor('all')
    void setActive('all')
    void setBookableNow('all')
    void setMaintenance('all')
    void setCheckInToday('all')
    void setCheckOutToday('all')
    void setGuest('')
    void setSearch('')
    void setOrdering('property')
    void setPage(1)
  }

  const changeFilter = (setter: (value: string) => unknown, value: string | null) => {
    if (!value) return
    void setter(value)
    void setPage(1)
  }

  const start = count === 0 ? 0 : (page - 1) * pageSize + 1
  const end = Math.min(page * pageSize, count)
  const occupancyOptions = [{ id: 'all', label: 'All' }, ...meta.occupancies.filter(item => item.id !== 'all')]
  const typeOptions = [{ id: 'all', label: 'All Types' }, ...meta.types]
  const statusOptions = [{ id: 'all', label: 'All Statuses' }, ...meta.statuses]

  return (
    <div className='flex flex-col gap-6'>
      <div>
        <h1 className='text-2xl font-semibold'>Availability</h1>
        <p className='text-muted-foreground text-sm'>
          Occupancy is calculated from reservations and stays (Free, Reserved, In house). Status is the operational
          condition set by staff and is never the same field.
        </p>
      </div>

      {error && (
        <Alert variant='destructive'>
          <AlertTitle>Unable to load availability.</AlertTitle>
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
              <CardTitle>Locations</CardTitle>
              <CardDescription>Free rooms can still be dirty or under maintenance. Use Available for booking for rooms that can take a new stay.</CardDescription>
            </div>
            <div className='flex w-full flex-col gap-2 lg:max-w-80'>
              <InputGroup>
                <InputGroupAddon>
                  <SearchIcon className='size-4' />
                </InputGroupAddon>
                <InputGroupInput
                  type='search'
                  placeholder='Search location, code, property...'
                  value={search}
                  onChange={event => {
                    void setSearch(event.target.value)
                    void setPage(1)
                  }}
                />
              </InputGroup>
              <InputGroup>
                <InputGroupInput
                  type='search'
                  placeholder='Current or next guest...'
                  value={guest}
                  onChange={event => {
                    void setGuest(event.target.value)
                    void setPage(1)
                  }}
                />
              </InputGroup>
            </div>
          </div>
          <div className='grid gap-3 sm:grid-cols-2 xl:grid-cols-4'>
            <FilterSelect label='Occupancy' value={occupancy} onValueChange={value => changeFilter(setOccupancy, value)}>
              {occupancyOptions.map(item => (
                <SelectItem key={item.id} value={item.id}>
                  {item.label}
                </SelectItem>
              ))}
            </FilterSelect>
            <FilterSelect label='Status' value={status} onValueChange={value => changeFilter(setStatus, value)}>
              {statusOptions.map(item => (
                <SelectItem key={item.id} value={item.id}>
                  {item.label}
                </SelectItem>
              ))}
            </FilterSelect>
            <FilterSelect label='Property' value={property} onValueChange={value => changeFilter(setProperty, value)}>
              <SelectItem value='all'>All Properties</SelectItem>
              {meta.properties.map((item: LocationProperty) => (
                <SelectItem key={item.id} value={String(item.id)}>
                  {item.name}
                </SelectItem>
              ))}
            </FilterSelect>
            <FilterSelect label='Type' value={type} onValueChange={value => changeFilter(setType, value)}>
              {typeOptions.map((item: LocationOption) => (
                <SelectItem key={item.id} value={item.id}>
                  {item.label}
                </SelectItem>
              ))}
            </FilterSelect>
            <FilterSelect label='Floor' value={floor} onValueChange={value => changeFilter(setFloor, value)}>
              <SelectItem value='all'>All Floors</SelectItem>
              {meta.floors.map(item => (
                <SelectItem key={item} value={item}>
                  {item}
                </SelectItem>
              ))}
            </FilterSelect>
            <FilterSelect label='Active' value={active} onValueChange={value => changeFilter(setActive, value)}>
              {ACTIVE_OPTIONS.map(item => (
                <SelectItem key={item.id} value={item.id}>
                  {item.label}
                </SelectItem>
              ))}
            </FilterSelect>
            <FilterSelect label='Available for booking' value={bookableNow} onValueChange={value => changeFilter(setBookableNow, value)}>
              {BOOKABLE_NOW_OPTIONS.map(item => (
                <SelectItem key={item.id} value={item.id}>
                  {item.label}
                </SelectItem>
              ))}
            </FilterSelect>
            <FilterSelect label='Maintenance' value={maintenance} onValueChange={value => changeFilter(setMaintenance, value)}>
              {YES_NO_OPTIONS.map(item => (
                <SelectItem key={item.id} value={item.id}>
                  {item.label}
                </SelectItem>
              ))}
            </FilterSelect>
            <FilterSelect label='Check-in today' value={checkInToday} onValueChange={value => changeFilter(setCheckInToday, value)}>
              {YES_NO_OPTIONS.map(item => (
                <SelectItem key={item.id} value={item.id}>
                  {item.label}
                </SelectItem>
              ))}
            </FilterSelect>
            <FilterSelect label='Check-out today' value={checkOutToday} onValueChange={value => changeFilter(setCheckOutToday, value)}>
              {YES_NO_OPTIONS.map(item => (
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
          </div>
        </CardHeader>
        <CardContent className='overflow-x-auto'>
          {loading && <p className='text-muted-foreground text-sm'>Loading availability…</p>}
          {!loading && error && <p className='text-muted-foreground text-sm'>Availability could not be loaded.</p>}
          {!loading && !error && items.length === 0 && (
            <div className='flex flex-col gap-3'>
              <p className='text-muted-foreground text-sm'>
                {filtersActive ? 'No locations match your filters.' : 'No locations found'}
              </p>
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
                  <TableHead>Location</TableHead>
                  <TableHead>Property</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Occupancy</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Current / next guest</TableHead>
                  <TableHead>Check-in</TableHead>
                  <TableHead>Check-out</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map(item => {
                  const guest = guestBooking(item)

                  return (
                  <TableRow key={item.id}>
                    <TableCell className='font-medium'>
                      <Link href={`/properties/${item.property.id}/locations/${item.id}`} className='hover:underline'>
                        {item.name}
                      </Link>
                      {item.code ? <span className='text-muted-foreground ml-2 text-xs'>{item.code}</span> : null}
                    </TableCell>
                    <TableCell>
                      <Link href={`/properties/${item.property.id}`} className='hover:underline'>
                        {item.property.name}
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
                    <TableCell>
                      {guest ? (
                        <Link href={`/bookings/${guest.id}`} className='hover:underline'>
                          {guest.customer.name}
                        </Link>
                      ) : (
                        <span className='text-muted-foreground'>—</span>
                      )}
                    </TableCell>
                    <TableCell>{guest?.check_in ? formatDueAt(guest.check_in) : '—'}</TableCell>
                    <TableCell>{guest?.check_out ? formatDueAt(guest.check_out) : '—'}</TableCell>
                    <TableCell>
                      <Link href={`/properties/${item.property.id}/locations/${item.id}`} className='hover:underline'>
                        Open
                      </Link>
                    </TableCell>
                  </TableRow>
                  )
                })}
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

    </div>
  )
}

export default AvailabilityPageView
