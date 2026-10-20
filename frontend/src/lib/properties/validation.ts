import type { Property, PropertyDraft } from '@/lib/properties/types'

export type PropertyFieldErrors = Partial<Record<keyof PropertyDraft, string>>

const RATE_PATTERN = /^-?\d+(\.\d+)?$/

export const emptyPropertyDraft = (): PropertyDraft => ({
  name: '',
  code: '',
  property_type: 'hotel',
  description: '',
  country: 'Malaysia',
  region: '',
  city: '',
  address_line1: '',
  address_line2: '',
  postal_code: '',
  phone: '',
  email: '',
  website: '',
  currency: 'MYR',
  rate: '',
  status: 'active',
  check_in_time: '15:00',
  check_out_time: '12:00',
  timezone: 'Asia/Kuala_Lumpur',
  star_rating: ''
})

export const draftFromProperty = (property: Property): PropertyDraft => ({
  name: property.name,
  code: property.code ?? '',
  property_type: property.property_type || 'hotel',
  description: property.description ?? '',
  country: property.country || 'Malaysia',
  region: property.region,
  city: property.city,
  address_line1: property.address_line1 ?? '',
  address_line2: property.address_line2 ?? '',
  postal_code: property.postal_code ?? '',
  phone: property.phone ?? '',
  email: property.email ?? '',
  website: property.website ?? '',
  currency: property.currency || 'MYR',
  rate: property.rate,
  status: property.status || 'active',
  check_in_time: property.check_in_time || '15:00',
  check_out_time: property.check_out_time || '12:00',
  timezone: property.timezone || 'Asia/Kuala_Lumpur',
  star_rating: property.star_rating == null ? '' : String(property.star_rating)
})

export const validatePropertyDraft = (draft: PropertyDraft): PropertyFieldErrors => {
  const errors: PropertyFieldErrors = {}

  if (!draft.name.trim()) errors.name = 'Property name is required.'
  if (!draft.region.trim()) errors.region = 'Region is required.'
  if (!draft.city.trim()) errors.city = 'City is required.'
  if (draft.email.trim() && !draft.email.includes('@')) errors.email = 'Enter a valid email address.'

  const rate = draft.rate.trim()

  if (!rate) {
    errors.rate = 'Rate is required.'
  } else if (!RATE_PATTERN.test(rate) || !Number.isFinite(Number(rate))) {
    errors.rate = 'Rate must be a valid number.'
  } else if (Number(rate) < 0) {
    errors.rate = 'Rate cannot be negative.'
  }

  const stars = draft.star_rating.trim()
  if (stars) {
    const numeric = Number(stars)
    if (!Number.isInteger(numeric) || numeric < 1 || numeric > 5) {
      errors.star_rating = 'Star rating must be between 1 and 5.'
    }
  }

  return errors
}

export const propertyPayloadFromDraft = (draft: PropertyDraft) => ({
  name: draft.name.trim(),
  code: draft.code.trim(),
  property_type: draft.property_type,
  description: draft.description.trim(),
  country: draft.country.trim() || 'Malaysia',
  region: draft.region.trim(),
  city: draft.city.trim(),
  address_line1: draft.address_line1.trim(),
  address_line2: draft.address_line2.trim(),
  postal_code: draft.postal_code.trim(),
  phone: draft.phone.trim(),
  email: draft.email.trim(),
  website: draft.website.trim(),
  currency: draft.currency.trim().toUpperCase() || 'MYR',
  rate: draft.rate.trim(),
  status: draft.status,
  check_in_time: draft.check_in_time,
  check_out_time: draft.check_out_time,
  timezone: draft.timezone.trim() || 'Asia/Kuala_Lumpur',
  star_rating: draft.star_rating.trim() === '' ? null : Number(draft.star_rating.trim())
})

export type PropertyWritePayload = ReturnType<typeof propertyPayloadFromDraft>

export const formatPropertyRate = (value: string | number, currency = 'MYR'): string => {
  const numeric = typeof value === 'number' ? value : Number(value)

  if (!Number.isFinite(numeric)) return String(value)

  return `${currency} ${numeric.toFixed(2)}`
}

export const formatPropertyAddress = (property: Pick<Property, 'address_line1' | 'address_line2' | 'city' | 'region' | 'country' | 'postal_code'>): string => {
  return [property.address_line1, property.address_line2, property.city, property.region, property.postal_code, property.country]
    .map(item => item?.trim())
    .filter(Boolean)
    .join(', ')
}
