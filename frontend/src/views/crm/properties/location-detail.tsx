'use client'

import { useEffect, useState } from 'react'

import Link from 'next/link'
import { useParams } from 'next/navigation'

import { useAuth } from '@/components/auth/auth-provider'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { isApiError } from '@/lib/api'
import { formatDueAt } from '@/lib/datetime'
import { locationsApi } from '@/lib/locations/api'
import { occupancyBadgeClass, statusBadgeClass } from '@/lib/locations/badges'
import type { Location } from '@/lib/locations/types'
import { formatLocationCapacity, formatLocationRate } from '@/lib/locations/validation'
import { cn } from '@/lib/utils'

import LocationFormDialog from './location-form-dialog'
import LocationOperationsDialogs from './location-operations-dialogs'

const ACTION_LABELS: Record<string, string> = {
  check_in: 'Check in',
  check_out: 'Check out',
  mark_available: 'Mark available',
  mark_dirty: 'Mark dirty',
  start_cleaning: 'Start cleaning',
  complete_cleaning: 'Complete cleaning',
  start_maintenance: 'Start maintenance',
  mark_out_of_order: 'Mark out of order',
  resolve_maintenance: 'Resolve maintenance',
  edit: 'Edit location'
}

const ACTION_PERMISSIONS: Record<string, string | string[]> = {
  check_in: 'locations.check_in',
  check_out: 'locations.check_out',
  mark_available: ['locations.change_status', 'properties.change_property'],
  mark_dirty: ['locations.change_status', 'properties.change_property'],
  start_cleaning: 'locations.manage_cleaning',
  complete_cleaning: 'locations.manage_cleaning',
  start_maintenance: 'locations.manage_maintenance',
  mark_out_of_order: 'locations.manage_maintenance',
  resolve_maintenance: 'locations.manage_maintenance',
  edit: 'properties.change_property'
}

const BookingLine = ({ booking, label }: { booking?: Location['current_booking']; label: string }) => {
  if (!booking) {
    return (
      <div>
        <dt className='text-muted-foreground'>{label}</dt>
        <dd className='text-muted-foreground'>None</dd>
      </div>
    )
  }

  return (
    <div>
      <dt className='text-muted-foreground'>{label}</dt>
      <dd className='font-medium'>
        <Link href={`/bookings/${booking.id}`} className='hover:underline'>
          {booking.customer.name}
        </Link>
        <span className='text-muted-foreground'> · {booking.case_number}</span>
        {booking.check_in ? <span className='text-muted-foreground'> · in {formatDueAt(booking.check_in)}</span> : null}
        {booking.check_out ? <span className='text-muted-foreground'> · out {formatDueAt(booking.check_out)}</span> : null}
      </dd>
    </div>
  )
}

const LocationDetailView = () => {
  const params = useParams<{ id: string; locationId: string }>()
  const propertyId = Number(params.id)
  const locationId = Number(params.locationId)
  const valid = Number.isInteger(propertyId) && propertyId > 0 && Number.isInteger(locationId) && locationId > 0
  const { can } = useAuth()
  const [location, setLocation] = useState<Location | null>(null)
  const [loading, setLoading] = useState(valid)
  const [error, setError] = useState<string | null>(valid ? null : 'Location not found.')
  const [action, setAction] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)

  const load = () =>
    locationsApi.get(locationId).then(payload => {
      setLocation(payload)
      setError(null)

      return payload
    })

  useEffect(() => {
    if (!valid) return

    let mounted = true

    load()
      .catch(err => {
        if (!mounted) return
        setLocation(null)
        setError(isApiError(err) ? err.message : 'Unable to load this location.')
      })
      .finally(() => {
        if (!mounted) return
        setLoading(false)
      })

    return () => {
      mounted = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locationId, valid])

  if (loading) {
    return <p className='text-muted-foreground text-sm'>Loading location…</p>
  }

  if (error || !location) {
    return (
      <Alert variant='destructive'>
        <AlertTitle>Unable to load location.</AlertTitle>
        <AlertDescription className='flex flex-col gap-3'>
          <span>{error || 'Location not found.'}</span>
          {valid && (
            <Button type='button' variant='outline' className='w-fit' onClick={() => void load().finally(() => setLoading(false))}>
              Retry
            </Button>
          )}
        </AlertDescription>
      </Alert>
    )
  }

  const actions = (location.allowed_actions || []).filter(item => {
    if (item === 'deactivate') return false

    const permission = ACTION_PERMISSIONS[item]

    return permission ? can(permission) : true
  })

  return (
    <div className='flex flex-col gap-6'>
      <div className='flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between'>
        <div>
          <p className='text-muted-foreground text-sm'>
            <Link href={`/properties/${location.property.id}?tab=locations`} className='hover:underline'>
              {location.property.name}
            </Link>
            <span> / Locations</span>
          </p>
          <h1 className='text-2xl font-semibold'>{location.name}</h1>
          <div className='mt-2 flex flex-wrap items-center gap-2'>
            <Badge variant='outline'>{location.type_label}</Badge>
            <Badge variant='outline' className={cn(occupancyBadgeClass(location.occupancy))}>
              {location.occupancy_label || location.occupancy || '—'}
            </Badge>
            <Badge variant='outline' className={cn(statusBadgeClass(location.status))}>
              {location.status_label}
            </Badge>
            {!location.active && <Badge variant='outline'>Inactive</Badge>}
          </div>
        </div>
        <div className='flex flex-wrap gap-2'>
          {actions.map(item => (
            <Button
              key={item}
              type='button'
              variant={item === 'check_out' || item === 'mark_out_of_order' ? 'outline' : 'default'}
              onClick={() => (item === 'edit' ? setEditing(true) : setAction(item))}
            >
              {ACTION_LABELS[item] || item}
            </Button>
          ))}
        </div>
      </div>

      <div className='grid gap-6 xl:grid-cols-2'>
        <Card className='shadow-none'>
          <CardHeader>
            <CardTitle>Location information</CardTitle>
            <CardDescription>Property inventory details for this bookable space.</CardDescription>
          </CardHeader>
          <CardContent>
            <dl className='grid gap-3 text-sm sm:grid-cols-2'>
              <div>
                <dt className='text-muted-foreground'>Name</dt>
                <dd className='font-medium'>{location.name}</dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Type</dt>
                <dd className='font-medium'>{location.type_label}</dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Property</dt>
                <dd className='font-medium'>{location.property.name}</dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Floor / area</dt>
                <dd className='font-medium'>{location.floor || '—'}</dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Capacity</dt>
                <dd className='font-medium'>{formatLocationCapacity(location.capacity)}</dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Rate</dt>
                <dd className='font-medium'>{formatLocationRate(location.base_rate, location.currency)}</dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Active</dt>
                <dd className='font-medium'>{location.active ? 'Yes' : 'No'}</dd>
              </div>
              <div className='sm:col-span-2'>
                <dt className='text-muted-foreground'>Description</dt>
                <dd className='font-medium'>{location.description || '—'}</dd>
              </div>
            </dl>
          </CardContent>
        </Card>

        <Card className='shadow-none'>
          <CardHeader>
            <CardTitle>Current state</CardTitle>
            <CardDescription>Occupancy comes from stays. Status is set by staff.</CardDescription>
          </CardHeader>
          <CardContent>
            <dl className='grid gap-3 text-sm sm:grid-cols-2'>
              <div>
                <dt className='text-muted-foreground'>Occupancy</dt>
                <dd>
                  <Badge variant='outline' className={cn(occupancyBadgeClass(location.occupancy))}>
                    {location.occupancy_label || location.occupancy || '—'}
                  </Badge>
                </dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Operational status</dt>
                <dd>
                  <Badge variant='outline' className={cn(statusBadgeClass(location.status))}>
                    {location.status_label}
                  </Badge>
                </dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Available for booking</dt>
                <dd className='font-medium'>{location.is_bookable_now ? 'Yes' : 'No'}</dd>
              </div>
              <BookingLine booking={location.current_booking} label='Current guest' />
              <BookingLine booking={location.upcoming_booking} label='Next guest' />
            </dl>
            {location.open_maintenance && (
              <div className='border-destructive/30 bg-destructive/5 mt-4 rounded-md border p-3 text-sm'>
                <p className='font-medium'>{location.open_maintenance.title}</p>
                <p className='text-muted-foreground'>
                  {location.open_maintenance.priority_label} · {location.open_maintenance.status_label}
                  {location.open_maintenance.description ? ` · ${location.open_maintenance.description}` : ''}
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className='shadow-none'>
        <CardHeader>
          <CardTitle>History</CardTitle>
          <CardDescription>Reservations, status changes, cleaning, and maintenance.</CardDescription>
        </CardHeader>
        <CardContent className='space-y-6'>
          <div>
            <h3 className='mb-2 text-sm font-medium'>Reservations</h3>
            <div className='space-y-2 text-sm'>
              {location.current_booking || location.upcoming_booking ? (
                [location.current_booking, location.upcoming_booking]
                  .filter((item, index, list) => item && list.findIndex(entry => entry?.id === item.id) === index)
                  .map(booking => (
                    <p key={booking!.id}>
                      <Link href={`/bookings/${booking!.id}`} className='hover:underline'>
                        {booking!.case_number} · {booking!.customer.name}
                      </Link>
                      {booking!.check_in ? ` · ${formatDueAt(booking!.check_in)}` : ''}
                      {booking!.actual_check_in ? ` · checked in ${formatDueAt(booking!.actual_check_in)}` : ''}
                      {booking!.actual_check_out ? ` · checked out ${formatDueAt(booking!.actual_check_out)}` : ''}
                    </p>
                  ))
              ) : (
                <p className='text-muted-foreground'>No current or upcoming reservations.</p>
              )}
            </div>
          </div>
          <div className='overflow-x-auto'>
            <h3 className='mb-2 text-sm font-medium'>Status changes</h3>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>When</TableHead>
                  <TableHead>From</TableHead>
                  <TableHead>To</TableHead>
                  <TableHead>By</TableHead>
                  <TableHead>Reason</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(location.status_history || []).length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className='text-muted-foreground'>
                      No status history yet.
                    </TableCell>
                  </TableRow>
                ) : (
                  location.status_history?.map(item => (
                    <TableRow key={item.id}>
                      <TableCell>{item.created_at ? formatDueAt(item.created_at) : '—'}</TableCell>
                      <TableCell>{item.previous_status || '—'}</TableCell>
                      <TableCell>{item.new_status}</TableCell>
                      <TableCell>{item.changed_by?.display_name || '—'}</TableCell>
                      <TableCell>{item.reason || '—'}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
          <div className='overflow-x-auto'>
            <h3 className='mb-2 text-sm font-medium'>Cleaning</h3>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Status</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead>Completed</TableHead>
                  <TableHead>Staff</TableHead>
                  <TableHead>Notes</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(location.cleaning_tasks || []).length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className='text-muted-foreground'>
                      No cleaning history yet.
                    </TableCell>
                  </TableRow>
                ) : (
                  location.cleaning_tasks?.map(item => (
                    <TableRow key={item.id}>
                      <TableCell>{item.status_label}</TableCell>
                      <TableCell>{item.started_at ? formatDueAt(item.started_at) : '—'}</TableCell>
                      <TableCell>{item.completed_at ? formatDueAt(item.completed_at) : '—'}</TableCell>
                      <TableCell>{item.assigned_to?.display_name || item.created_by?.display_name || '—'}</TableCell>
                      <TableCell>{item.notes || '—'}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
          <div className='overflow-x-auto'>
            <h3 className='mb-2 text-sm font-medium'>Maintenance</h3>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Issue</TableHead>
                  <TableHead>Priority</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead>Resolved</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(location.maintenance_issues || []).length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className='text-muted-foreground'>
                      No maintenance history yet.
                    </TableCell>
                  </TableRow>
                ) : (
                  location.maintenance_issues?.map(item => (
                    <TableRow key={item.id}>
                      <TableCell>
                        <p className='font-medium'>{item.title}</p>
                        {item.description ? <p className='text-muted-foreground text-xs'>{item.description}</p> : null}
                      </TableCell>
                      <TableCell>{item.priority_label}</TableCell>
                      <TableCell>{item.status_label}</TableCell>
                      <TableCell>{item.started_at ? formatDueAt(item.started_at) : '—'}</TableCell>
                      <TableCell>{item.resolved_at ? formatDueAt(item.resolved_at) : '—'}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <LocationFormDialog
        open={editing}
        propertyId={location.property.id}
        location={location}
        onOpenChange={setEditing}
        onSaved={setLocation}
      />
      <LocationOperationsDialogs
        location={location}
        action={action}
        canOverride={can(['locations.override_check_in', 'payments.verify_payment'])}
        onOpenChange={open => !open && setAction(null)}
        onUpdated={setLocation}
      />
    </div>
  )
}

export default LocationDetailView
