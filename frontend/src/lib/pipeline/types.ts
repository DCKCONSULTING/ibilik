import type { Channel, CustomerIdentity, CustomerStatus } from '@/lib/customers/types'

export const PIPELINE_STAGE_ORDER = ['new', 'qualified', 'quoted', 'negotiating', 'won', 'lost'] as const

export type PipelineStage = (typeof PIPELINE_STAGE_ORDER)[number]

export type PipelineStageDefinition = {
  id: PipelineStage
  label: string
  order: number
}

export const PIPELINE_STAGES: PipelineStageDefinition[] = [
  { id: 'new', label: 'New', order: 1 },
  { id: 'qualified', label: 'Qualified', order: 2 },
  { id: 'quoted', label: 'Quoted', order: 3 },
  { id: 'negotiating', label: 'Negotiating', order: 4 },
  { id: 'won', label: 'Won', order: 5 },
  { id: 'lost', label: 'Lost', order: 6 }
]

export type WorkflowAction = 'qualify' | 'quote' | 'approve' | 'move_to_finance' | 'reopen'

export type FinanceStatus = 'none' | 'sent'

export type PipelineCustomer = {
  id: number
  name: string
  email: string
  phone: string
  status?: CustomerStatus
  identities?: CustomerIdentity[]
}

export type PipelineProperty = {
  id: number
  name: string
}

export type PipelineLocation = {
  id: number
  name: string
  code: string
  type: string
  type_label: string
}

export type PipelineUser = {
  id: number
  username: string
  name?: string
  display_name: string
}

export type OpportunityMessage = {
  id: number
  sender_type: string
  sender_name: string
  content: string
  created_at: string | null
}

export type OpportunityConversation = {
  id: number
  channel: Channel | string
  channel_label: string
  subject: string
  messages?: OpportunityMessage[]
}

export type FollowUpStatus = 'pending' | 'completed' | 'cancelled' | 'overdue'

export type FollowUpTypeId =
  | 'call_customer'
  | 'send_quote'
  | 'follow_up'
  | 'request_information'
  | 'check_availability'
  | 'internal_review'
  | 'payment_follow_up'
  | 'other'

export const FOLLOW_UP_TYPES: { id: FollowUpTypeId; label: string }[] = [
  { id: 'call_customer', label: 'Call Customer' },
  { id: 'send_quote', label: 'Send Quote' },
  { id: 'follow_up', label: 'Follow Up' },
  { id: 'request_information', label: 'Request Information' },
  { id: 'check_availability', label: 'Check Availability' },
  { id: 'internal_review', label: 'Internal Review' },
  { id: 'payment_follow_up', label: 'Payment Follow Up' },
  { id: 'other', label: 'Other' }
]

export type CaseFollowUp = {
  id: number
  case_id: number
  type: FollowUpTypeId | string
  type_label: string
  title: string
  description: string
  status: FollowUpStatus | string
  status_label: string
  assigned_to: PipelineUser | null
  created_by?: PipelineUser | null
  due_at: string | null
  completed_at: string | null
  created_at: string | null
  updated_at: string | null
  case?: {
    id: number
    case_number: string
    title: string
    stage: PipelineStage | string
    stage_label: string
    source: Channel | string | null
    source_label: string | null
  }
  customer?: PipelineCustomer
  property?: PipelineProperty | null
}

export type FollowUpListResponse = {
  resource: string
  count: number
  page: number
  page_size: number
  has_next: boolean
  actionable_count: number
  types: { id: string; label: string }[]
  stages: PipelineStageDefinition[]
  sources: { id: string; label: string }[]
  staff: PipelineUser[]
  properties: PipelineProperty[]
  results: CaseFollowUp[]
}

export type CaseActivity = {
  id: number
  event_type: string
  message: string
  actor: PipelineUser | null
  created_at: string | null
}

export type Opportunity = {
  id: number
  case_number: string
  title: string
  description: string
  request: string
  request_preview: string
  original_request?: string
  stage: PipelineStage
  stage_label: string
  value: string | null
  quote_notes: string
  staff_notes?: string
  finance_status: FinanceStatus
  finance_status_label?: string
  source: Channel | string | null
  source_label: string | null
  allowed_actions: WorkflowAction[]
  customer: PipelineCustomer
  property: PipelineProperty | null
  location?: PipelineLocation | null
  assigned_to: PipelineUser | null
  assigned_user: PipelineUser | null
  assigned_staff?: PipelineUser | null
  created_by: PipelineUser | null
  conversation_id: number | null
  conversation: OpportunityConversation | null
  conversations?: OpportunityConversation[]
  messages?: OpportunityMessage[]
  next_follow_up: CaseFollowUp | null
  follow_ups?: CaseFollowUp[]
  activities?: CaseActivity[]
  quoted_at?: string | null
  approved_at?: string | null
  finance_moved_at?: string | null
  check_in?: string | null
  check_out?: string | null
  closed_at?: string | null
  created_at: string | null
  updated_at: string | null
}

export type Case = Opportunity

export type PipelineListResponse = {
  resource: string
  count: number
  page: number
  page_size: number
  has_next: boolean
  stages: PipelineStageDefinition[]
  follow_up_types?: { id: string; label: string }[]
  stage_counts: Record<PipelineStage, number>
  total_value: string | null
  open_value: string | null
  results: Opportunity[]
}

export type OpportunityDraft = {
  title: string
  description: string
  customer_id: string
  property_id: string
  stage: PipelineStage
  value: string
}

export type WorkflowActionPayload = {
  action: WorkflowAction
  value?: string
  notes?: string
}
