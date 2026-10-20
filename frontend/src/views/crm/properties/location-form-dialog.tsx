'use client'

import { useState } from 'react'

import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog'
import { Field, FieldError, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { isApiError } from '@/lib/api'
import { locationsApi } from '@/lib/locations/api'
import { BED_TYPES, LOCATION_STATUSES, LOCATION_TYPES, type Location, type LocationDraft } from '@/lib/locations/types'
import { draftFromLocation, emptyLocationDraft, validateLocationDraft } from '@/lib/locations/validation'

type LocationFormDialogProps = {
  open: boolean
  propertyId: number
  location?: Location | null
  types?: { id: string; label: string }[]
  statuses?: { id: string; label: string }[]
  onOpenChange: (open: boolean) => void
  onSaved: (location: Location) => void
}

type LocationFormFieldsProps = {
  propertyId: number
  location?: Location | null
  types: { id: string; label: string }[]
  statuses: { id: string; label: string }[]
  onClose: () => void
  onSaved: (location: Location) => void
}

const LocationFormFields = ({ propertyId, location, types, statuses, onClose, onSaved }: LocationFormFieldsProps) => {
  const [draft, setDraft] = useState<LocationDraft>(location ? draftFromLocation(location) : emptyLocationDraft())
  const [errors, setErrors] = useState<ReturnType<typeof validateLocationDraft>>({})
  const [submitting, setSubmitting] = useState(false)
  const isEdit = location != null

  const submit = async () => {
    const nextErrors = validateLocationDraft(draft)

    setErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) return

    setSubmitting(true)

    try {
      const payload: LocationDraft = {
        ...draft,
        name: draft.name.trim(),
        code: draft.code.trim(),
        description: draft.description.trim()
      }

      const saved = isEdit
        ? await locationsApi.update(location.id, payload)
        : await locationsApi.create(propertyId, payload)

      toast.success(isEdit ? 'Location updated.' : 'Location created.')
      onSaved(saved)
      onClose()
    } catch (error) {
      toast.error(isApiError(error) ? error.message : 'Unable to save the location.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <FieldGroup className='gap-4'>
        <Field data-invalid={Boolean(errors.name)}>
          <FieldLabel htmlFor='location-name'>Name</FieldLabel>
          <Input
            id='location-name'
            value={draft.name}
            aria-invalid={Boolean(errors.name)}
            onChange={event => setDraft(current => ({ ...current, name: event.target.value }))}
          />
          {errors.name && <FieldError>{errors.name}</FieldError>}
        </Field>
        <Field>
          <FieldLabel htmlFor='location-code'>Code</FieldLabel>
          <Input
            id='location-code'
            value={draft.code}
            placeholder='101'
            onChange={event => setDraft(current => ({ ...current, code: event.target.value }))}
          />
        </Field>
        <Field data-invalid={Boolean(errors.type)}>
          <FieldLabel>Type</FieldLabel>
          <Select value={draft.type} onValueChange={value => value && setDraft(current => ({ ...current, type: value }))}>
            <SelectTrigger className='w-full'>
              <SelectValue placeholder='Select a type' />
            </SelectTrigger>
            <SelectContent>
              {types.map(item => (
                <SelectItem key={item.id} value={item.id}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {errors.type && <FieldError>{errors.type}</FieldError>}
        </Field>
        <Field data-invalid={Boolean(errors.capacity)}>
          <FieldLabel htmlFor='location-capacity'>Capacity</FieldLabel>
          <Input
            id='location-capacity'
            inputMode='numeric'
            value={draft.capacity}
            aria-invalid={Boolean(errors.capacity)}
            onChange={event => setDraft(current => ({ ...current, capacity: event.target.value }))}
          />
          {errors.capacity && <FieldError>{errors.capacity}</FieldError>}
        </Field>
        <div className='grid gap-4 sm:grid-cols-2'>
          <Field data-invalid={Boolean(errors.max_adults)}>
            <FieldLabel htmlFor='location-adults'>Max adults</FieldLabel>
            <Input
              id='location-adults'
              inputMode='numeric'
              value={draft.max_adults}
              aria-invalid={Boolean(errors.max_adults)}
              onChange={event => setDraft(current => ({ ...current, max_adults: event.target.value }))}
            />
            {errors.max_adults && <FieldError>{errors.max_adults}</FieldError>}
          </Field>
          <Field data-invalid={Boolean(errors.max_children)}>
            <FieldLabel htmlFor='location-children'>Max children</FieldLabel>
            <Input
              id='location-children'
              inputMode='numeric'
              value={draft.max_children}
              aria-invalid={Boolean(errors.max_children)}
              onChange={event => setDraft(current => ({ ...current, max_children: event.target.value }))}
            />
            {errors.max_children && <FieldError>{errors.max_children}</FieldError>}
          </Field>
          <Field>
            <FieldLabel htmlFor='location-floor'>Floor</FieldLabel>
            <Input
              id='location-floor'
              value={draft.floor}
              onChange={event => setDraft(current => ({ ...current, floor: event.target.value }))}
            />
          </Field>
          <Field>
            <FieldLabel>Bed type</FieldLabel>
            <Select value={draft.bed_type} onValueChange={value => value && setDraft(current => ({ ...current, bed_type: value }))}>
              <SelectTrigger className='w-full'>
                <SelectValue placeholder='Select a bed type' />
              </SelectTrigger>
              <SelectContent>
                {BED_TYPES.map(item => (
                  <SelectItem key={item.id} value={item.id}>
                    {item.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <Field data-invalid={Boolean(errors.bed_count)}>
            <FieldLabel htmlFor='location-beds'>Bed count</FieldLabel>
            <Input
              id='location-beds'
              inputMode='numeric'
              value={draft.bed_count}
              aria-invalid={Boolean(errors.bed_count)}
              onChange={event => setDraft(current => ({ ...current, bed_count: event.target.value }))}
            />
            {errors.bed_count && <FieldError>{errors.bed_count}</FieldError>}
          </Field>
          <Field data-invalid={Boolean(errors.size_sqm)}>
            <FieldLabel htmlFor='location-size'>Size (sqm)</FieldLabel>
            <Input
              id='location-size'
              inputMode='decimal'
              value={draft.size_sqm}
              aria-invalid={Boolean(errors.size_sqm)}
              onChange={event => setDraft(current => ({ ...current, size_sqm: event.target.value }))}
            />
            {errors.size_sqm && <FieldError>{errors.size_sqm}</FieldError>}
          </Field>
          <Field data-invalid={Boolean(errors.base_rate)}>
            <FieldLabel htmlFor='location-rate'>Base rate</FieldLabel>
            <Input
              id='location-rate'
              inputMode='decimal'
              value={draft.base_rate}
              aria-invalid={Boolean(errors.base_rate)}
              onChange={event => setDraft(current => ({ ...current, base_rate: event.target.value }))}
            />
            {errors.base_rate && <FieldError>{errors.base_rate}</FieldError>}
          </Field>
          <Field>
            <FieldLabel htmlFor='location-currency'>Currency</FieldLabel>
            <Input
              id='location-currency'
              value={draft.currency}
              onChange={event => setDraft(current => ({ ...current, currency: event.target.value }))}
            />
          </Field>
        </div>
        <Field>
          <FieldLabel htmlFor='location-description'>Description</FieldLabel>
          <Textarea
            id='location-description'
            value={draft.description}
            onChange={event => setDraft(current => ({ ...current, description: event.target.value }))}
          />
        </Field>
        <Field>
          <FieldLabel>Status</FieldLabel>
          <Select value={draft.status} onValueChange={value => value && setDraft(current => ({ ...current, status: value }))}>
            <SelectTrigger className='w-full'>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {statuses.map(item => (
                <SelectItem key={item.id} value={item.id}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        <Field orientation='horizontal' className='items-center justify-between'>
          <FieldLabel htmlFor='location-bookable'>Bookable</FieldLabel>
          <Switch
            id='location-bookable'
            checked={draft.is_bookable}
            onCheckedChange={checked => setDraft(current => ({ ...current, is_bookable: checked }))}
          />
        </Field>
        <Field orientation='horizontal' className='items-center justify-between'>
          <FieldLabel htmlFor='location-active'>Active</FieldLabel>
          <Switch
            id='location-active'
            checked={draft.active}
            onCheckedChange={checked => setDraft(current => ({ ...current, active: checked }))}
          />
        </Field>
      </FieldGroup>
      <DialogFooter>
        <Button variant='outline' onClick={onClose}>
          Cancel
        </Button>
        <Button onClick={() => void submit()} disabled={submitting}>
          {submitting ? 'Saving…' : isEdit ? 'Save Location' : 'Add Location'}
        </Button>
      </DialogFooter>
    </>
  )
}

const LocationFormDialog = ({
  open,
  propertyId,
  location,
  types = [...LOCATION_TYPES],
  statuses = [...LOCATION_STATUSES],
  onOpenChange,
  onSaved
}: LocationFormDialogProps) => {
  const isEdit = location != null

  return (
    <Dialog
      open={open}
      onOpenChange={next => {
        if (!next) onOpenChange(false)
        else onOpenChange(true)
      }}
    >
      <DialogContent className='max-h-[min(100dvh,42rem)] overflow-y-auto sm:max-w-2xl'>
        <DialogHeader>
          <DialogTitle>{isEdit ? 'Edit Location' : 'Add Location'}</DialogTitle>
        </DialogHeader>
        {open && (
          <LocationFormFields
            key={location?.id ?? 'new'}
            propertyId={propertyId}
            location={location}
            types={types}
            statuses={statuses}
            onClose={() => onOpenChange(false)}
            onSaved={onSaved}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

export default LocationFormDialog
