'use client'

import { useState } from 'react'

import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog'
import { Field, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { isApiError } from '@/lib/api'
import { locationsApi } from '@/lib/locations/api'
import type { Location } from '@/lib/locations/types'

type LocationOperationsDialogsProps = {
  location: Location
  action: string | null
  onOpenChange: (open: boolean) => void
  onUpdated: (location: Location) => void
  canOverride?: boolean
}

const guestName = (location: Location) =>
  location.current_booking?.customer.name || location.upcoming_booking?.customer.name || 'the guest'

const LocationOperationsDialogs = ({
  location,
  action,
  onOpenChange,
  onUpdated,
  canOverride
}: LocationOperationsDialogsProps) => {
  const [notes, setNotes] = useState('')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState('medium')
  const [override, setOverride] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const close = () => {
    setNotes('')
    setTitle('')
    setDescription('')
    setPriority('medium')
    setOverride(false)
    onOpenChange(false)
  }

  const run = async (task: () => Promise<Location>, success: string) => {
    setSubmitting(true)

    try {
      const next = await task()

      toast.success(success)
      onUpdated(next)
      close()
    } catch (error) {
      toast.error(isApiError(error) ? error.message : 'Unable to update this location.')
    } finally {
      setSubmitting(false)
    }
  }

  const reservation = location.upcoming_booking || location.case
  const stay = location.current_booking

  const outstanding = Number(stay?.outstanding || 0)

  const checkoutNeedsOverride = action === 'check_out' && outstanding > 0

  const needsOverride =
    (action === 'check_in' &&
      ['maintenance', 'out_of_order', 'inactive', 'dirty', 'cleaning', 'inspection'].includes(location.status)) ||
    checkoutNeedsOverride

  const titleForAction = {
    check_in: 'Check in',
    check_out: 'Check out',
    mark_available: 'Mark available',
    mark_dirty: 'Mark dirty',
    start_cleaning: 'Start cleaning',
    complete_cleaning: 'Complete cleaning',
    start_maintenance: 'Start maintenance',
    mark_out_of_order: 'Mark out of order',
    resolve_maintenance: 'Resolve maintenance',
    deactivate: 'Deactivate location'
  }[action ?? '']

  if (!action || !titleForAction) return null

  const submit = () => {
    if (action === 'check_in') {
      return run(
        () => locationsApi.checkIn(location.id, { case_id: reservation?.id, override: override && canOverride }),
        'Guest checked in.'
      )
    }

    if (action === 'check_out') {
      return run(() => locationsApi.checkOut(location.id, { case_id: stay?.id, override }), 'Guest checked out.')
    }

    if (action === 'mark_available') {
      return run(() => locationsApi.setStatus(location.id, { status: 'available', reason: notes }), 'Location marked available.')
    }

    if (action === 'mark_dirty') {
      return run(() => locationsApi.setStatus(location.id, { status: 'dirty', reason: notes }), 'Location marked dirty.')
    }

    if (action === 'start_cleaning') {
      return run(() => locationsApi.startCleaning(location.id, { notes }), 'Cleaning started.')
    }

    if (action === 'complete_cleaning') {
      return run(() => locationsApi.completeCleaning(location.id, { notes }), 'Cleaning completed.')
    }

    if (action === 'start_maintenance' || action === 'mark_out_of_order') {
      return run(
        () =>
          locationsApi.startMaintenance(location.id, {
            title: title || (action === 'mark_out_of_order' ? 'Out of order' : 'Maintenance'),
            description,
            priority,
            out_of_order: action === 'mark_out_of_order'
          }),
        action === 'mark_out_of_order' ? 'Location marked out of order.' : 'Maintenance started.'
      )
    }

    if (action === 'resolve_maintenance') {
      return run(
        () => locationsApi.resolveMaintenance(location.id, { issue_id: location.open_maintenance?.id, notes }),
        'Maintenance resolved.'
      )
    }

    if (action === 'deactivate') {
      return run(() => locationsApi.deactivate(location.id), 'Location deactivated.')
    }

    return undefined
  }

  return (
    <Dialog open onOpenChange={open => !open && close()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{titleForAction}</DialogTitle>
          <DialogDescription>
            {location.name} · occupancy {location.occupancy_label || location.occupancy || '—'} · status {location.status_label}
          </DialogDescription>
        </DialogHeader>
        <div className='space-y-4'>
          {action === 'check_in' && (
            <p className='text-sm'>
              Check in {guestName(location)}
              {reservation?.check_in ? ` for ${new Date(reservation.check_in).toLocaleString()}` : ''}. Occupancy will
              become In house.
            </p>
          )}
          {action === 'check_out' && (
            <div className='space-y-2 text-sm'>
              <p>
                Check out {guestName(location)}. The stay will close and the location will be marked Dirty. This does not
                mark the account as paid.
              </p>
              {outstanding > 0 && (
                <p className='text-destructive'>
                  Outstanding balance {stay?.outstanding}. Settle payment before check-out, or use an authorized override.
                </p>
              )}
            </div>
          )}
          {needsOverride && (
            <p className='text-destructive text-sm'>
              Check-in is blocked while this location is {location.status_label.toLowerCase()}.
              {canOverride ? ' Confirm override to continue.' : ' A manager override is required.'}
            </p>
          )}
          {(action === 'start_maintenance' || action === 'mark_out_of_order') && (
            <>
              <Field>
                <FieldLabel htmlFor='maintenance-title'>Issue title</FieldLabel>
                <Input
                  id='maintenance-title'
                  value={title}
                  onChange={event => setTitle(event.target.value)}
                  placeholder={action === 'mark_out_of_order' ? 'Out of order' : 'Issue title'}
                />
              </Field>
              <Field>
                <FieldLabel htmlFor='maintenance-description'>Description</FieldLabel>
                <Textarea
                  id='maintenance-description'
                  value={description}
                  onChange={event => setDescription(event.target.value)}
                />
              </Field>
              <Field>
                <FieldLabel>Priority</FieldLabel>
                <Select value={priority} onValueChange={value => value && setPriority(value)}>
                  <SelectTrigger className='w-full'>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value='low'>Low</SelectItem>
                    <SelectItem value='medium'>Medium</SelectItem>
                    <SelectItem value='high'>High</SelectItem>
                    <SelectItem value='urgent'>Urgent</SelectItem>
                  </SelectContent>
                </Select>
              </Field>
              <p className='text-muted-foreground text-sm'>Existing reservations stay in place. New conflicting bookings will be blocked.</p>
            </>
          )}
          {['mark_available', 'mark_dirty', 'start_cleaning', 'complete_cleaning', 'resolve_maintenance'].includes(action) && (
            <Field>
              <FieldLabel htmlFor='location-notes'>Notes</FieldLabel>
              <Textarea id='location-notes' value={notes} onChange={event => setNotes(event.target.value)} />
            </Field>
          )}
          {needsOverride && canOverride && (
            <label className='flex items-center gap-2 text-sm'>
              <input type='checkbox' checked={override} onChange={event => setOverride(event.target.checked)} />
              {checkoutNeedsOverride ? 'Authorize outstanding-balance override' : 'Authorize check-in override'}
            </label>
          )}
        </div>
        <DialogFooter>
          <Button type='button' variant='outline' onClick={close}>
            Cancel
          </Button>
          <Button
            type='button'
            disabled={
              submitting || (needsOverride && !canOverride) || (needsOverride && canOverride && !override)
            }
            onClick={() => void submit()}
          >
            Confirm
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default LocationOperationsDialogs
