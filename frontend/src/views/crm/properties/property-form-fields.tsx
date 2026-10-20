'use client'

import { Field, FieldError, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { PROPERTY_STATUSES, PROPERTY_TYPES, type PropertyDraft } from '@/lib/properties/types'
import type { PropertyFieldErrors } from '@/lib/properties/validation'

type PropertyFormFieldsProps = {
  draft: PropertyDraft
  errors: PropertyFieldErrors
  idPrefix: string
  onChange: (patch: Partial<PropertyDraft>) => void
}

const PropertyFormFields = ({ draft, errors, idPrefix, onChange }: PropertyFormFieldsProps) => {
  const fieldId = (name: string) => `${idPrefix}-${name}`

  return (
    <FieldGroup className='gap-4'>
      <Field data-invalid={Boolean(errors.name)}>
        <FieldLabel htmlFor={fieldId('name')}>Hotel name</FieldLabel>
        <Input
          id={fieldId('name')}
          value={draft.name}
          aria-invalid={Boolean(errors.name)}
          onChange={event => onChange({ name: event.target.value })}
        />
        {errors.name && <FieldError>{errors.name}</FieldError>}
      </Field>
      <div className='grid gap-4 sm:grid-cols-2'>
        <Field>
          <FieldLabel htmlFor={fieldId('code')}>Code</FieldLabel>
          <Input id={fieldId('code')} value={draft.code} onChange={event => onChange({ code: event.target.value })} />
        </Field>
        <Field>
          <FieldLabel>Property type</FieldLabel>
          <Select value={draft.property_type} onValueChange={value => value && onChange({ property_type: value })}>
            <SelectTrigger className='w-full'>
              <SelectValue placeholder='Select a type' />
            </SelectTrigger>
            <SelectContent>
              {PROPERTY_TYPES.map(item => (
                <SelectItem key={item.id} value={item.id}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
      </div>
      <Field>
        <FieldLabel htmlFor={fieldId('description')}>Description</FieldLabel>
        <Textarea
          id={fieldId('description')}
          value={draft.description}
          onChange={event => onChange({ description: event.target.value })}
        />
      </Field>
      <div className='grid gap-4 sm:grid-cols-2'>
        <Field>
          <FieldLabel htmlFor={fieldId('country')}>Country</FieldLabel>
          <Input id={fieldId('country')} value={draft.country} onChange={event => onChange({ country: event.target.value })} />
        </Field>
        <Field data-invalid={Boolean(errors.region)}>
          <FieldLabel htmlFor={fieldId('region')}>Region</FieldLabel>
          <Input
            id={fieldId('region')}
            value={draft.region}
            aria-invalid={Boolean(errors.region)}
            onChange={event => onChange({ region: event.target.value })}
          />
          {errors.region && <FieldError>{errors.region}</FieldError>}
        </Field>
        <Field data-invalid={Boolean(errors.city)}>
          <FieldLabel htmlFor={fieldId('city')}>City</FieldLabel>
          <Input
            id={fieldId('city')}
            value={draft.city}
            aria-invalid={Boolean(errors.city)}
            onChange={event => onChange({ city: event.target.value })}
          />
          {errors.city && <FieldError>{errors.city}</FieldError>}
        </Field>
        <Field>
          <FieldLabel htmlFor={fieldId('postal')}>Postal code</FieldLabel>
          <Input
            id={fieldId('postal')}
            value={draft.postal_code}
            onChange={event => onChange({ postal_code: event.target.value })}
          />
        </Field>
      </div>
      <Field>
        <FieldLabel htmlFor={fieldId('address1')}>Address line 1</FieldLabel>
        <Input
          id={fieldId('address1')}
          value={draft.address_line1}
          onChange={event => onChange({ address_line1: event.target.value })}
        />
      </Field>
      <Field>
        <FieldLabel htmlFor={fieldId('address2')}>Address line 2</FieldLabel>
        <Input
          id={fieldId('address2')}
          value={draft.address_line2}
          onChange={event => onChange({ address_line2: event.target.value })}
        />
      </Field>
      <div className='grid gap-4 sm:grid-cols-2'>
        <Field>
          <FieldLabel htmlFor={fieldId('phone')}>Phone</FieldLabel>
          <Input id={fieldId('phone')} value={draft.phone} onChange={event => onChange({ phone: event.target.value })} />
        </Field>
        <Field data-invalid={Boolean(errors.email)}>
          <FieldLabel htmlFor={fieldId('email')}>Email</FieldLabel>
          <Input
            id={fieldId('email')}
            type='email'
            value={draft.email}
            aria-invalid={Boolean(errors.email)}
            onChange={event => onChange({ email: event.target.value })}
          />
          {errors.email && <FieldError>{errors.email}</FieldError>}
        </Field>
      </div>
      <Field>
        <FieldLabel htmlFor={fieldId('website')}>Website</FieldLabel>
        <Input id={fieldId('website')} value={draft.website} onChange={event => onChange({ website: event.target.value })} />
      </Field>
      <div className='grid gap-4 sm:grid-cols-2'>
        <Field>
          <FieldLabel htmlFor={fieldId('currency')}>Currency</FieldLabel>
          <Input
            id={fieldId('currency')}
            value={draft.currency}
            onChange={event => onChange({ currency: event.target.value })}
          />
        </Field>
        <Field data-invalid={Boolean(errors.rate)}>
          <FieldLabel htmlFor={fieldId('rate')}>Base rate</FieldLabel>
          <Input
            id={fieldId('rate')}
            inputMode='decimal'
            value={draft.rate}
            aria-invalid={Boolean(errors.rate)}
            onChange={event => onChange({ rate: event.target.value })}
          />
          {errors.rate && <FieldError>{errors.rate}</FieldError>}
        </Field>
        <Field>
          <FieldLabel>Status</FieldLabel>
          <Select value={draft.status} onValueChange={value => value && onChange({ status: value })}>
            <SelectTrigger className='w-full'>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PROPERTY_STATUSES.map(item => (
                <SelectItem key={item.id} value={item.id}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        <Field data-invalid={Boolean(errors.star_rating)}>
          <FieldLabel htmlFor={fieldId('stars')}>Star rating</FieldLabel>
          <Input
            id={fieldId('stars')}
            inputMode='numeric'
            value={draft.star_rating}
            aria-invalid={Boolean(errors.star_rating)}
            onChange={event => onChange({ star_rating: event.target.value })}
          />
          {errors.star_rating && <FieldError>{errors.star_rating}</FieldError>}
        </Field>
        <Field>
          <FieldLabel htmlFor={fieldId('checkin')}>Check-in</FieldLabel>
          <Input
            id={fieldId('checkin')}
            type='time'
            value={draft.check_in_time}
            onChange={event => onChange({ check_in_time: event.target.value })}
          />
        </Field>
        <Field>
          <FieldLabel htmlFor={fieldId('checkout')}>Check-out</FieldLabel>
          <Input
            id={fieldId('checkout')}
            type='time'
            value={draft.check_out_time}
            onChange={event => onChange({ check_out_time: event.target.value })}
          />
        </Field>
      </div>
      <Field>
        <FieldLabel htmlFor={fieldId('timezone')}>Timezone</FieldLabel>
        <Input
          id={fieldId('timezone')}
          value={draft.timezone}
          onChange={event => onChange({ timezone: event.target.value })}
        />
      </Field>
    </FieldGroup>
  )
}

export default PropertyFormFields
