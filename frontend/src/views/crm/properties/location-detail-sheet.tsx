'use client'

import Link from 'next/link'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { occupancyBadgeClass, statusBadgeClass } from '@/lib/locations/badges'
import type { Location } from '@/lib/locations/types'
import { formatLocationCapacity, formatLocationRate } from '@/lib/locations/validation'
import { cn } from '@/lib/utils'

type LocationDetailSheetProps = {
  location: Location | null
  canEdit?: boolean
  onOpenChange: (open: boolean) => void
  onEdit?: (location: Location) => void
  onDeactivate?: (location: Location) => void
}

const BookingBlock = ({ title, booking }: { title: string; booking: Location['current_booking'] }) => {
  if (!booking) {
    return (
      <div>
        <dt className='text-muted-foreground'>{title}</dt>
        <dd className='text-muted-foreground'>None</dd>
      </div>
    )
  }

  return (
    <div className='sm:col-span-2'>
      <dt className='text-muted-foreground'>{title}</dt>
      <dd className='font-medium'>
        <Link href={`/bookings/${booking.id}`} className='hover:underline'>
          {booking.case_number} · {booking.customer.name}
        </Link>
        {booking.check_in ? ` · ${new Date(booking.check_in).toLocaleString()}` : ''}
      </dd>
    </div>
  )
}

const LocationDetailSheet = ({ location, canEdit, onOpenChange, onEdit, onDeactivate }: LocationDetailSheetProps) => {
  return (
    <Sheet open={location !== null} onOpenChange={open => !open && onOpenChange(false)}>
      <SheetContent className='overflow-y-auto sm:max-w-lg'>
        <SheetHeader>
          <SheetTitle>{location?.name ?? 'Location'}</SheetTitle>
        </SheetHeader>
        {location && (
          <div className='flex flex-col gap-6 px-4 pb-6'>
            <div className='flex flex-wrap items-center gap-2'>
              <Badge variant='outline'>{location.type_label}</Badge>
              <Badge variant='outline' className={cn(occupancyBadgeClass(location.occupancy))}>
                {location.occupancy_label || location.occupancy || '—'}
              </Badge>
              <Badge variant='outline' className={cn(statusBadgeClass(location.status))}>
                {location.status_label}
              </Badge>
              {!location.active && <Badge variant='outline'>Inactive</Badge>}
            </div>
            <dl className='grid gap-3 text-sm sm:grid-cols-2'>
              <div>
                <dt className='text-muted-foreground'>Property</dt>
                <dd className='font-medium'>{location.property.name}</dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Type</dt>
                <dd className='font-medium'>{location.type_label}</dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Code</dt>
                <dd className='font-medium'>{location.code || '—'}</dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Capacity</dt>
                <dd className='font-medium'>{formatLocationCapacity(location.capacity)}</dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Max adults / children</dt>
                <dd className='font-medium'>
                  {formatLocationCapacity(location.max_adults)} / {formatLocationCapacity(location.max_children)}
                </dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Floor</dt>
                <dd className='font-medium'>{location.floor || '—'}</dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Bed</dt>
                <dd className='font-medium'>
                  {location.bed_type_label || location.bed_type || '—'}
                  {location.bed_count ? ` × ${location.bed_count}` : ''}
                </dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Base rate</dt>
                <dd className='font-medium'>{formatLocationRate(location.base_rate, location.currency)}</dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Occupancy</dt>
                <dd className='font-medium'>{location.occupancy_label || location.occupancy || '—'}</dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Status</dt>
                <dd className='font-medium'>{location.status_label}</dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Available for booking</dt>
                <dd className='font-medium'>{location.is_bookable_now ? 'Yes' : 'No'}</dd>
              </div>
              <div>
                <dt className='text-muted-foreground'>Active</dt>
                <dd className='font-medium'>{location.active ? 'Yes' : 'No'}</dd>
              </div>
              <div className='sm:col-span-2'>
                <dt className='text-muted-foreground'>Description</dt>
                <dd className='font-medium'>{location.description || '—'}</dd>
              </div>
              <BookingBlock title='Current guest' booking={location.current_booking} />
              <BookingBlock title='Next guest' booking={location.upcoming_booking} />
            </dl>
            <div className='flex flex-wrap gap-2'>
              <Link href={`/properties/${location.property.id}/locations/${location.id}`} className='text-sm font-medium hover:underline'>
                Manage location
              </Link>
              {canEdit && onEdit && (
                <Button variant='outline' onClick={() => onEdit(location)}>
                  Edit
                </Button>
              )}
              {canEdit && location.active && onDeactivate && (
                <Button variant='ghost' onClick={() => onDeactivate(location)}>
                  Deactivate
                </Button>
              )}
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}

export default LocationDetailSheet
