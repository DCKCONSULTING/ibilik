export const LOCATION_TYPES = [
  { id: 'room', label: 'Room' },
  { id: 'table', label: 'Table' },
  { id: 'meeting_room', label: 'Meeting Room' },
  { id: 'villa', label: 'Villa' },
  { id: 'apartment', label: 'Apartment' },
  { id: 'suite', label: 'Suite' },
  { id: 'parking', label: 'Parking' },
  { id: 'desk', label: 'Desk' },
  { id: 'other', label: 'Other' }
] as const

export const LOCATION_STATUSES = [
  { id: 'available', label: 'Available' },
  { id: 'dirty', label: 'Dirty' },
  { id: 'cleaning', label: 'Cleaning' },
  { id: 'maintenance', label: 'Maintenance' },
  { id: 'out_of_order', label: 'Out of order' },
  { id: 'inspection', label: 'Inspection' },
  { id: 'inactive', label: 'Inactive' }
] as const

export const LOCATION_OCCUPANCIES = [
  { id: 'free', label: 'Free' },
  { id: 'reserved', label: 'Reserved' },
  { id: 'in_house', label: 'In house' }
] as const

export const BED_TYPES = [
  { id: 'none', label: 'None' },
  { id: 'king', label: 'King' },
  { id: 'queen', label: 'Queen' },
  { id: 'twin', label: 'Twin' },
  { id: 'double', label: 'Double' },
  { id: 'single', label: 'Single' },
  { id: 'sofa', label: 'Sofa' },
  { id: 'other', label: 'Other' }
] as const

export type LocationType = (typeof LOCATION_TYPES)[number]['id']
export type LocationStatus = (typeof LOCATION_STATUSES)[number]['id']
export type LocationOccupancy = (typeof LOCATION_OCCUPANCIES)[number]['id']

export type LocationProperty = {
  id: number
  name: string
}

export type LocationCustomer = {
  id: number
  name: string
  email: string
  phone: string
}

export type LocationUser = {
  id: number
  username: string
  name: string
  display_name: string
}

export type LocationBooking = {
  id: number
  case_number: string
  title: string
  stage: string
  check_in: string | null
  check_out: string | null
  actual_check_in?: string | null
  actual_check_out?: string | null
  customer: LocationCustomer
  outstanding?: string | null
  account_status?: string
  account_status_label?: string
}

export type LocationStatusHistory = {
  id: number
  previous_status: string
  new_status: string
  reason: string
  changed_by: LocationUser | null
  created_at: string | null
}

export type LocationCleaningTask = {
  id: number
  status: string
  status_label: string
  notes: string
  assigned_to: LocationUser | null
  created_by: LocationUser | null
  started_at: string | null
  completed_at: string | null
  created_at: string | null
}

export type LocationMaintenanceIssue = {
  id: number
  title: string
  description: string
  priority: string
  priority_label: string
  status: string
  status_label: string
  notes: string
  assigned_to: LocationUser | null
  created_by: LocationUser | null
  started_at: string | null
  expected_at: string | null
  resolved_at: string | null
  created_at: string | null
}

export type Location = {
  id: number
  property: LocationProperty
  property_id: number
  name: string
  code: string
  type: LocationType | string
  type_label: string
  description: string
  capacity: number | null
  max_adults: number | null
  max_children: number | null
  floor: string
  bed_type: string
  bed_type_label: string
  bed_count: number | null
  base_rate: string | null
  currency: string
  status: LocationStatus | string
  status_label: string
  is_bookable: boolean
  amenities: string[]
  size_sqm: string | null
  active: boolean
  occupancy?: LocationOccupancy | string
  occupancy_label?: string
  is_free?: boolean
  is_bookable_now?: boolean
  allowed_actions?: string[]
  created_at: string | null
  updated_at: string | null
  current_booking?: LocationBooking | null
  upcoming_booking?: LocationBooking | null
  case?: LocationBooking | null
  customer?: LocationCustomer | null
  status_history?: LocationStatusHistory[]
  cleaning_tasks?: LocationCleaningTask[]
  maintenance_issues?: LocationMaintenanceIssue[]
  open_maintenance?: LocationMaintenanceIssue | null
}

export type LocationOption = {
  id: string
  label: string
}

export type LocationListResponse = {
  resource: string
  property: LocationProperty
  types: LocationOption[]
  statuses: LocationOption[]
  occupancies?: LocationOption[]
  results: Location[]
}

export type LocationDraft = {
  name: string
  code: string
  type: LocationType | string
  capacity: string
  max_adults: string
  max_children: string
  floor: string
  bed_type: string
  bed_count: string
  base_rate: string
  currency: string
  description: string
  status: LocationStatus | string
  is_bookable: boolean
  size_sqm: string
  active: boolean
}

export type LocationListQuery = {
  type?: string
  status?: string
  occupancy?: string
  active?: string
  search?: string
}
