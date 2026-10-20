'use client'

import { useState } from 'react'

import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { isApiError } from '@/lib/api'
import { propertiesApi } from '@/lib/properties/api'
import type { Property, PropertyDraft } from '@/lib/properties/types'
import {
  draftFromProperty,
  formatPropertyAddress,
  formatPropertyRate,
  propertyPayloadFromDraft,
  validatePropertyDraft
} from '@/lib/properties/validation'

import PropertyFormFields from './property-form-fields'

type PropertyGeneralSectionProps = {
  property: Property
  canEdit: boolean
  onUpdated: (property: Property) => void
}

const DetailItem = ({ label, value }: { label: string; value: string | number | null | undefined }) => (
  <div>
    <dt className='text-muted-foreground'>{label}</dt>
    <dd className='font-medium'>{value || '—'}</dd>
  </div>
)

const PropertyGeneralSection = ({ property, canEdit, onUpdated }: PropertyGeneralSectionProps) => {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<PropertyDraft>(draftFromProperty(property))
  const [errors, setErrors] = useState<ReturnType<typeof validatePropertyDraft>>({})
  const [saving, setSaving] = useState(false)

  const startEdit = () => {
    setDraft(draftFromProperty(property))
    setErrors({})
    setEditing(true)
  }

  const cancel = () => {
    setDraft(draftFromProperty(property))
    setErrors({})
    setEditing(false)
  }

  const save = async () => {
    const nextErrors = validatePropertyDraft(draft)

    setErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) return

    setSaving(true)

    try {
      const saved = await propertiesApi.update(property.id, propertyPayloadFromDraft(draft))

      toast.success('Property updated.')
      onUpdated(saved)
      setEditing(false)
    } catch (error) {
      toast.error(isApiError(error) ? error.message : 'Unable to update the property.')
    } finally {
      setSaving(false)
    }
  }

  if (!editing) {
    return (
      <section className='space-y-4'>
        <div className='flex items-center justify-between gap-3'>
          <div>
            <h3 className='font-medium'>General</h3>
            <p className='text-muted-foreground text-sm'>Hotel identity, address, contact, and operating details.</p>
          </div>
          {canEdit && (
            <Button variant='outline' onClick={startEdit}>
              Edit
            </Button>
          )}
        </div>
        <dl className='grid gap-3 text-sm sm:grid-cols-2'>
          <DetailItem label='Hotel name' value={property.name} />
          <DetailItem label='Code' value={property.code} />
          <DetailItem label='Property type' value={property.property_type_label} />
          <DetailItem label='Status' value={property.status_label} />
          <div className='sm:col-span-2'>
            <dt className='text-muted-foreground'>Address</dt>
            <dd className='font-medium'>{formatPropertyAddress(property) || '—'}</dd>
          </div>
          <DetailItem label='City / region' value={[property.city, property.region].filter(Boolean).join(', ')} />
          <DetailItem label='Country' value={property.country} />
          <DetailItem label='Phone' value={property.phone} />
          <DetailItem label='Email' value={property.email} />
          <DetailItem label='Website' value={property.website} />
          <DetailItem label='Currency' value={property.currency} />
          <DetailItem label='Base rate' value={formatPropertyRate(property.rate, property.currency)} />
          <DetailItem label='Check-in' value={property.check_in_time} />
          <DetailItem label='Check-out' value={property.check_out_time} />
          <DetailItem label='Timezone' value={property.timezone} />
          <DetailItem label='Star rating' value={property.star_rating} />
          <div className='sm:col-span-2'>
            <dt className='text-muted-foreground'>Description</dt>
            <dd className='font-medium'>{property.description || '—'}</dd>
          </div>
        </dl>
      </section>
    )
  }

  return (
    <section className='space-y-4'>
      <div>
        <h3 className='font-medium'>General</h3>
        <p className='text-muted-foreground text-sm'>Update the property details and save.</p>
      </div>
      <PropertyFormFields
        draft={draft}
        errors={errors}
        idPrefix='general'
        onChange={patch => setDraft(current => ({ ...current, ...patch }))}
      />
      <div className='flex flex-wrap gap-2'>
        <Button onClick={() => void save()} disabled={saving}>
          {saving ? 'Saving…' : 'Save'}
        </Button>
        <Button variant='outline' onClick={cancel} disabled={saving}>
          Cancel
        </Button>
      </div>
    </section>
  )
}

export default PropertyGeneralSection
