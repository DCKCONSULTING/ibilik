import type { PipelineProperty, PipelineUser } from '@/lib/pipeline/types'

export type MatchStatus = 'new' | 'unassigned' | 'assigned' | 'in_progress' | 'waiting' | 'resolved' | 'cancelled'
export type MatchPriority = 'low' | 'normal' | 'high' | 'urgent'
export type MatchRequestType =
  | 'booking'
  | 'quote'
  | 'payment'
  | 'inquiry'
  | 'property'
  | 'cancellation'
  | 'modification'
  | 'other'

export type MatchStaff = PipelineUser & {
  role?: string | null
  role_name?: string | null
  is_active?: boolean
  assigned_properties?: PipelineProperty[]
}

export type MatchRelatedRecord = {
  kind: 'case' | 'booking' | 'quote' | 'payment' | string
  id: number
  number: string
  label: string
  title?: string
}

export type MatchHistoryEntry = {
  id: number
  action: string
  action_label: string
  previous_value: string
  new_value: string
  actor: PipelineUser | null
  created_at: string | null
}

export type MatchNote = {
  id: number
  body: string
  created_by: PipelineUser | null
  created_at: string | null
}

export type MatchRequest = {
  id: number
  request_number: string
  request_type: MatchRequestType | string
  request_type_label: string
  source_module: string
  source_ref: string
  subject: string
  description: string
  priority: MatchPriority | string
  priority_label: string
  status: MatchStatus | string
  status_label: string
  customer: {
    id: number
    name: string
    email: string
    phone: string
    status?: string
  } | null
  property: PipelineProperty | null
  location: { id: number; name: string; code: string } | null
  related_record: MatchRelatedRecord | null
  related_case: { id: number; case_number: string; title: string; stage: string } | null
  related_quote: { id: number; quote_number: string; status: string } | null
  related_payment: { id: number; payment_number: string; status: string; amount: string; currency: string } | null
  assigned_to: MatchStaff | null
  assigned_by: MatchStaff | null
  assigned_at: string | null
  assignment_method?: 'automatic' | 'manual' | 'reassigned' | string | null
  assignment_method_label?: string | null
  workload_at_assignment?: number | null
  assigned_to_workload?: number | null
  unassigned_reason?: string | null
  due_at: string | null
  is_overdue: boolean
  internal_notes: string
  resolution_notes: string
  created_by: PipelineUser | null
  created_at: string | null
  updated_at: string | null
  notes?: MatchNote[]
  history?: MatchHistoryEntry[]
  assignable_staff?: MatchStaff[]
}

export type MatchSummary = {
  new: number
  unassigned: number
  assigned: number
  in_progress: number
  urgent: number
  resolved: number
  new_unassigned_count: number
}

export type MatchListResponse = {
  resource: string
  count: number
  page: number
  page_size: number
  has_next: boolean
  summary: MatchSummary
  new_unassigned_count: number
  statuses: { id: string; label: string }[]
  types: { id: string; label: string }[]
  priorities: { id: string; label: string }[]
  staff: MatchStaff[]
  properties: PipelineProperty[]
  results: MatchRequest[]
}

export type MatchSummaryResponse = MatchSummary & {
  resource: string
}

export type MatchAssignmentMethod = 'automatic' | 'manual' | 'reassigned'

export type MatchSettings = {
  resource?: string
  auto_assign_enabled: boolean
  property_staff_only: boolean
  org_wide_when_no_property: boolean
  assignment_mode: string
  assignment_mode_label: string
  updated_at: string | null
}

export type MatchWorkloadRow = {
  id: number
  username: string
  name: string
  display_name: string
  active_requests: number
  last_assigned_at: string | null
  eligible: boolean
  assigned_properties: PipelineProperty[]
}

export type MatchWorkloadResponse = {
  resource: string
  count: number
  property: PipelineProperty | null
  results: MatchWorkloadRow[]
}
