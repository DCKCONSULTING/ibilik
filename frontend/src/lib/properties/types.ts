export type PropertyStaffRole = {
  id: string
  name: string
  code: string
}

export type PropertyStaffManager = {
  id: number
  name: string
  role: PropertyStaffRole | null
}

export type PropertyStaff = {
  id: number
  username: string
  display_name: string
  first_name: string
  last_name: string
  email?: string
  is_active: boolean
  role?: PropertyStaffRole | null
  reports_to?: PropertyStaffManager | null
  assigned_at?: string | null
  reports?: PropertyStaff[]
}

export type PropertyStaffListResponse = {
  results: PropertyStaff[]
  roles: PropertyStaffRole[]
  hierarchy: PropertyStaff[]
}

export type PropertySummary = {
  location_count: number
  available_count: number
  occupied_count: number
  upcoming_bookings_count: number
  open_cases_count: number
  pending_quotes_count: number
  booking_count: number
  case_count: number
  quote_count: number
}

export const PROPERTY_TYPES = [
  { id: 'hotel', label: 'Hotel' },
  { id: 'resort', label: 'Resort' },
  { id: 'boutique_hotel', label: 'Boutique Hotel' },
  { id: 'business_hotel', label: 'Business Hotel' },
  { id: 'villa', label: 'Villa' },
  { id: 'apartment', label: 'Apartment' },
  { id: 'hostel', label: 'Hostel' },
  { id: 'guesthouse', label: 'Guesthouse' }
] as const

export const PROPERTY_STATUSES = [
  { id: 'active', label: 'Active' },
  { id: 'inactive', label: 'Inactive' }
] as const

export type PropertyType = (typeof PROPERTY_TYPES)[number]['id']
export type PropertyStatus = (typeof PROPERTY_STATUSES)[number]['id']

export type Property = {
  id: number
  name: string
  code: string
  property_type: PropertyType | string
  property_type_label: string
  description: string
  country: string
  region: string
  city: string
  address_line1: string
  address_line2: string
  postal_code: string
  latitude: string | null
  longitude: string | null
  phone: string
  email: string
  website: string
  currency: string
  rate: string
  base_rate: string
  status: PropertyStatus | string
  status_label: string
  check_in_time: string | null
  check_out_time: string | null
  timezone: string
  star_rating: number | null
  amenities: string[]
  staff_count: number
  location_count: number
  created_at: string | null
  updated_at: string | null
  staff?: PropertyStaff[]
  summary?: PropertySummary
}

export type PropertyListResponse = {
  resource: string
  results: Property[]
}

export type ExcelImportMode = 'properties' | 'locations' | 'portfolio'

export type ExcelImportIssue = {
  sheet: string
  row: number
  column: string
  level: 'error' | 'warning'
  message: string
}

export type ExcelImportRow = {
  row: number
  action: 'create' | 'update'
  id: number | null
  property_id?: number | null
  name: string
  errors: string[]
  warnings: string[]
}

export type ExcelImportPreview = {
  resource: string
  valid: boolean
  mode: ExcelImportMode | string
  summary: {
    properties_create: number
    properties_update: number
    properties_errors: number
    locations_create: number
    locations_update: number
    locations_errors: number
    warnings: number
    errors: number
  }
  properties: ExcelImportRow[]
  locations: ExcelImportRow[]
  issues: ExcelImportIssue[]
}

export type ExcelImportResult = {
  ok: boolean
  mode: string
  created_properties: number[]
  updated_properties: number[]
  created_locations: number[]
  updated_locations: number[]
}

export type PropertyDraft = {
  name: string
  code: string
  property_type: string
  description: string
  country: string
  region: string
  city: string
  address_line1: string
  address_line2: string
  postal_code: string
  phone: string
  email: string
  website: string
  currency: string
  rate: string
  status: string
  check_in_time: string
  check_out_time: string
  timezone: string
  star_rating: string
}
