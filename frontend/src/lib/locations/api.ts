import { api } from '@/lib/api'
import type { Location, LocationDraft, LocationListQuery, LocationListResponse } from '@/lib/locations/types'

const optionalNumber = (value?: string | null) => {
  if (value == null || value === '') return null

  return Number(value)
}

const toPayload = (draft: Partial<LocationDraft>) => ({
  name: draft.name,
  code: draft.code,
  type: draft.type,
  capacity: optionalNumber(draft.capacity),
  max_adults: optionalNumber(draft.max_adults),
  max_children: optionalNumber(draft.max_children),
  floor: draft.floor,
  bed_type: draft.bed_type === 'none' ? '' : draft.bed_type,
  bed_count: optionalNumber(draft.bed_count),
  base_rate: draft.base_rate === '' || draft.base_rate == null ? null : draft.base_rate,
  currency: draft.currency,
  description: draft.description,
  status: draft.status,
  is_bookable: draft.is_bookable,
  size_sqm: draft.size_sqm === '' || draft.size_sqm == null ? null : draft.size_sqm,
  active: draft.active
})

export const locationsApi = {
  list(propertyId: number, query?: LocationListQuery) {
    return api.get<LocationListResponse>(`/api/properties/${propertyId}/locations/`, { query })
  },
  get(id: number) {
    return api.get<Location>(`/api/locations/${id}/`)
  },
  create(propertyId: number, payload: LocationDraft) {
    return api.post<Location>(`/api/properties/${propertyId}/locations/`, toPayload(payload))
  },
  update(id: number, payload: Partial<LocationDraft>) {
    return api.patch<Location>(`/api/locations/${id}/`, toPayload(payload))
  },
  deactivate(id: number) {
    return api.post<Location>(`/api/locations/${id}/deactivate/`)
  },
  checkIn(id: number, payload: { case_id?: number; override?: boolean }) {
    return api.post<Location>(`/api/locations/${id}/check-in/`, payload)
  },
  checkOut(id: number, payload?: { case_id?: number; override?: boolean }) {
    return api.post<Location>(`/api/locations/${id}/check-out/`, payload ?? {})
  },
  setStatus(id: number, payload: { status: string; reason?: string }) {
    return api.post<Location>(`/api/locations/${id}/status/`, payload)
  },
  startCleaning(id: number, payload?: { notes?: string; assigned_to?: number }) {
    return api.post<Location>(`/api/locations/${id}/cleaning/start/`, payload ?? {})
  },
  completeCleaning(id: number, payload?: { notes?: string }) {
    return api.post<Location>(`/api/locations/${id}/cleaning/complete/`, payload ?? {})
  },
  startMaintenance(
    id: number,
    payload: {
      title: string
      description?: string
      priority?: string
      assigned_to?: number
      expected_at?: string
      out_of_order?: boolean
    }
  ) {
    return api.post<Location>(`/api/locations/${id}/maintenance/`, payload)
  },
  resolveMaintenance(id: number, payload?: { issue_id?: number; notes?: string }) {
    return api.post<Location>(`/api/locations/${id}/maintenance/resolve/`, payload ?? {})
  }
}
