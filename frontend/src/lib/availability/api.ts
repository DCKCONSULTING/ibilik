import { api } from '@/lib/api'
import type { Location, LocationOption, LocationProperty } from '@/lib/locations/types'

export type AvailabilityListResponse = {
  resource: string
  count: number
  page: number
  page_size: number
  has_next: boolean
  types: LocationOption[]
  statuses: LocationOption[]
  occupancies: LocationOption[]
  properties: LocationProperty[]
  floors: string[]
  results: Location[]
}

export type AvailabilityListQuery = Record<string, string | number | boolean | undefined>

export const availabilityApi = {
  list(query?: AvailabilityListQuery) {
    return api.get<AvailabilityListResponse>('/api/availability/', { query })
  }
}
