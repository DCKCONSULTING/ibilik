import { api } from '@/lib/api'
import type {
  MatchListResponse,
  MatchRequest,
  MatchSettings,
  MatchSummaryResponse,
  MatchWorkloadResponse
} from '@/lib/match/types'

export const matchApi = {
  list(query?: Record<string, string | number | boolean | undefined>) {
    return api.get<MatchListResponse>('/api/match/requests/', { query })
  },
  summary() {
    return api.get<MatchSummaryResponse>('/api/match/summary/')
  },
  get(id: number) {
    return api.get<MatchRequest>(`/api/match/requests/${id}/`)
  },
  update(id: number, payload: { status?: string; priority?: string; resolution_notes?: string; due_at?: string | null }) {
    return api.patch<MatchRequest>(`/api/match/requests/${id}/`, payload)
  },
  assign(id: number, assignedToId: number) {
    return api.post<MatchRequest>(`/api/match/requests/${id}/assign/`, { assigned_to_id: assignedToId })
  },
  reassign(id: number, assignedToId: number) {
    return api.post<MatchRequest>(`/api/match/requests/${id}/reassign/`, { assigned_to_id: assignedToId })
  },
  unassign(id: number) {
    return api.post<MatchRequest>(`/api/match/requests/${id}/unassign/`)
  },
  assignAutomatically(id: number) {
    return api.post<MatchRequest>(`/api/match/requests/${id}/assign-automatically/`)
  },
  workload(propertyId?: string | number) {
    return api.get<MatchWorkloadResponse>('/api/match/staff-workload/', {
      query: propertyId != null && propertyId !== 'all' ? { property: propertyId } : undefined
    })
  },
  settings() {
    return api.get<MatchSettings>('/api/match/settings/')
  },
  updateSettings(payload: Partial<Pick<MatchSettings, 'auto_assign_enabled' | 'property_staff_only' | 'org_wide_when_no_property'>>) {
    return api.patch<MatchSettings>('/api/match/settings/', payload)
  },
  addNote(id: number, note: string) {
    return api.post<MatchRequest>(`/api/match/requests/${id}/notes/`, { note })
  },
  history(id: number) {
    return api.get<{ resource: string; count: number; results: NonNullable<MatchRequest['history']> }>(
      `/api/match/requests/${id}/history/`
    )
  }
}
