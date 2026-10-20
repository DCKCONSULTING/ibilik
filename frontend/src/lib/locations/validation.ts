import { LOCATION_STATUSES, LOCATION_TYPES, type Location, type LocationDraft } from '@/lib/locations/types'

export type LocationFieldErrors = Partial<Record<keyof LocationDraft, string>>

const CAPACITY_PATTERN = /^\d+$/
const RATE_PATTERN = /^-?\d+(\.\d+)?$/

export const emptyLocationDraft = (): LocationDraft => ({
  name: '',
  code: '',
  type: 'room',
  capacity: '',
  max_adults: '',
  max_children: '',
  floor: '',
  bed_type: 'none',
  bed_count: '',
  base_rate: '',
  currency: 'MYR',
  description: '',
  status: 'available',
  is_bookable: true,
  size_sqm: '',
  active: true
})

export const draftFromLocation = (location: Location): LocationDraft => ({
  name: location.name,
  code: location.code,
  type: location.type,
  capacity: location.capacity == null ? '' : String(location.capacity),
  max_adults: location.max_adults == null ? '' : String(location.max_adults),
  max_children: location.max_children == null ? '' : String(location.max_children),
  floor: location.floor ?? '',
  bed_type: location.bed_type || 'none',
  bed_count: location.bed_count == null ? '' : String(location.bed_count),
  base_rate: location.base_rate ?? '',
  currency: location.currency || 'MYR',
  description: location.description,
  status: location.status,
  is_bookable: location.is_bookable !== false,
  size_sqm: location.size_sqm ?? '',
  active: location.active
})

const validatePositiveInteger = (value: string, label: string, allowZero = false): string | undefined => {
  const text = value.trim()

  if (!text) return undefined
  if (!CAPACITY_PATTERN.test(text)) return `${label} must be a valid integer.`

  const numeric = Number(text)

  if (allowZero ? numeric < 0 : numeric < 1) {
    return allowZero ? `${label} cannot be negative.` : `${label} must be a positive integer.`
  }

  return undefined
}

export const validateLocationDraft = (draft: LocationDraft): LocationFieldErrors => {
  const errors: LocationFieldErrors = {}

  if (!draft.name.trim()) errors.name = 'Location name is required.'
  if (!draft.type) errors.type = 'Type is required.'

  const capacityError = validatePositiveInteger(draft.capacity, 'Capacity')
  if (capacityError) errors.capacity = capacityError

  const adultsError = validatePositiveInteger(draft.max_adults, 'Max adults')
  if (adultsError) errors.max_adults = adultsError

  const childrenError = validatePositiveInteger(draft.max_children, 'Max children', true)
  if (childrenError) errors.max_children = childrenError

  const bedsError = validatePositiveInteger(draft.bed_count, 'Bed count')
  if (bedsError) errors.bed_count = bedsError

  const rate = draft.base_rate.trim()
  if (rate) {
    if (!RATE_PATTERN.test(rate) || !Number.isFinite(Number(rate))) {
      errors.base_rate = 'Rate must be a valid number.'
    } else if (Number(rate) < 0) {
      errors.base_rate = 'Rate cannot be negative.'
    }
  }

  const size = draft.size_sqm.trim()
  if (size) {
    if (!RATE_PATTERN.test(size) || !Number.isFinite(Number(size))) {
      errors.size_sqm = 'Size must be a valid number.'
    } else if (Number(size) < 0) {
      errors.size_sqm = 'Size cannot be negative.'
    }
  }

  return errors
}

export const locationTypeLabel = (value: string, options = LOCATION_TYPES): string => {
  return options.find(item => item.id === value)?.label ?? value
}

export const locationStatusLabel = (value: string, options = LOCATION_STATUSES): string => {
  return options.find(item => item.id === value)?.label ?? value
}

export const formatLocationCapacity = (value: number | null | undefined): string => {
  if (value == null) return '—'

  return String(value)
}

export const formatLocationRate = (value: string | number | null | undefined, currency = 'MYR'): string => {
  if (value == null || value === '') return '—'

  const numeric = typeof value === 'number' ? value : Number(value)

  if (!Number.isFinite(numeric)) return String(value)

  return `${currency} ${numeric.toFixed(2)}`
}
