import { api } from '@/lib/api'
import type {
  CaseActivity,
  CaseFollowUp,
  FollowUpListResponse,
  FollowUpTypeId,
  Opportunity,
  OpportunityDraft,
  PipelineListResponse,
  PipelineStage,
  WorkflowActionPayload
} from '@/lib/pipeline/types'

export type FollowUpDraft = {
  case_id?: number
  type?: FollowUpTypeId | string
  title?: string
  description?: string
  assigned_to_id?: number | null
  due_at?: string | null
  status?: string
}

export const casesApi = {
  list(query?: Record<string, string | number | boolean | undefined>) {
    return api.get<PipelineListResponse>('/api/cases/', { query })
  },
  get(id: number) {
    return api.get<Opportunity>(`/api/cases/${id}/`)
  },
  create(payload: {
    title: string
    description?: string
    original_request?: string
    customer_id: number
    property_id?: number
    stage?: PipelineStage
    value?: string
    assigned_to_id?: number
  }) {
    return api.post<Opportunity>('/api/cases/', payload)
  },
  update(id: number, payload: Partial<Omit<OpportunityDraft, 'customer_id' | 'property_id'>> & {
    customer_id?: number
    property_id?: number | null
    assigned_to_id?: number | null
    staff_notes?: string
  }) {
    return api.patch<Opportunity>(`/api/cases/${id}/`, payload)
  },
  updateStage(id: number, stage: PipelineStage) {
    return api.patch<Opportunity>(`/api/cases/${id}/stage/`, { stage })
  },
  performAction(id: number, payload: WorkflowActionPayload) {
    return api.post<Opportunity>(`/api/cases/${id}/actions/`, payload)
  },
  remove(id: number) {
    return api.delete<{ ok: boolean }>(`/api/cases/${id}/`)
  },
  listFollowUps(caseId: number) {
    return api.get<{ results: CaseFollowUp[] }>(`/api/cases/${caseId}/follow-ups/`)
  },
  createFollowUp(caseId: number, payload: FollowUpDraft) {
    return api.post<CaseFollowUp>(`/api/cases/${caseId}/follow-ups/`, payload)
  },
  updateFollowUp(caseId: number, followUpId: number, payload: FollowUpDraft) {
    return api.patch<CaseFollowUp>(`/api/cases/${caseId}/follow-ups/${followUpId}/`, payload)
  },
  completeFollowUp(caseId: number, followUpId: number) {
    return api.post<CaseFollowUp>(`/api/cases/${caseId}/follow-ups/${followUpId}/complete/`)
  },
  cancelFollowUp(caseId: number, followUpId: number) {
    return api.delete<{ ok: boolean }>(`/api/cases/${caseId}/follow-ups/${followUpId}/`)
  },
  listActivities(caseId: number) {
    return api.get<{ results: CaseActivity[] }>(`/api/cases/${caseId}/activities/`)
  }
}

export const followUpsApi = {
  list(query?: Record<string, string | number | boolean | undefined>) {
    return api.get<FollowUpListResponse>('/api/follow-ups/', { query })
  },
  get(id: number) {
    return api.get<CaseFollowUp>(`/api/follow-ups/${id}/`)
  },
  create(payload: FollowUpDraft & { case_id: number }) {
    return api.post<CaseFollowUp>('/api/follow-ups/', payload)
  },
  update(id: number, payload: FollowUpDraft) {
    return api.patch<CaseFollowUp>(`/api/follow-ups/${id}/`, payload)
  },
  complete(id: number) {
    return api.post<CaseFollowUp>(`/api/follow-ups/${id}/complete/`)
  },
  cancel(id: number) {
    return api.delete<{ ok: boolean }>(`/api/follow-ups/${id}/`)
  }
}

export const activitiesApi = {
  list: casesApi.listActivities
}

export const pipelineApi = {
  list(query?: Record<string, string | number | boolean | undefined>) {
    return api.get<PipelineListResponse>('/api/pipeline/', { query })
  },
  get(id: number) {
    return api.get<Opportunity>(`/api/pipeline/${id}/`)
  },
  create(payload: {
    title: string
    description?: string
    customer_id: number
    property_id?: number
    stage?: PipelineStage
    value?: string
    assigned_to_id?: number
  }) {
    return api.post<Opportunity>('/api/pipeline/', payload)
  },
  update(id: number, payload: Partial<Omit<OpportunityDraft, 'customer_id' | 'property_id'>> & {
    customer_id?: number
    property_id?: number | null
    assigned_to_id?: number | null
    staff_notes?: string
  }) {
    return api.patch<Opportunity>(`/api/pipeline/${id}/`, payload)
  },
  updateStage(id: number, stage: PipelineStage) {
    return api.patch<Opportunity>(`/api/pipeline/${id}/stage/`, { stage })
  },
  performAction(id: number, payload: WorkflowActionPayload) {
    return api.post<Opportunity>(`/api/pipeline/${id}/actions/`, payload)
  },
  remove(id: number) {
    return api.delete<{ ok: boolean }>(`/api/pipeline/${id}/`)
  },
  listFollowUps: casesApi.listFollowUps,
  createFollowUp: casesApi.createFollowUp,
  updateFollowUp: casesApi.updateFollowUp,
  completeFollowUp: casesApi.completeFollowUp,
  cancelFollowUp: casesApi.cancelFollowUp,
  listActivities: casesApi.listActivities
}
