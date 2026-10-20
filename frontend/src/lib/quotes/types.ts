import type { PipelineProperty, PipelineUser } from '@/lib/pipeline/types'

export type QuoteWorkflowStatus = 'pending' | 'accepted' | 'rejected' | 'cancelled'
export type QuoteDisplayStatus = QuoteWorkflowStatus | 'expired'

export type Quote = {
  id: number
  quote_number: string
  amount: string | null
  amount_label: string | null
  currency: string
  workflow_status: QuoteWorkflowStatus | string
  status: QuoteDisplayStatus | string
  status_label: string
  is_expired: boolean
  valid_until: string | null
  notes: string
  created_by: PipelineUser | null
  created_at: string | null
  updated_at: string | null
  case: {
    id: number
    case_number: string
    title: string
    stage: string
    value?: string | null
    quote_notes?: string
  }
  customer: {
    id: number
    name: string
    email: string
    phone: string
  }
  property: PipelineProperty | null
  staff: PipelineUser | null
}

export type QuoteListResponse = {
  resource: string
  count: number
  page: number
  page_size: number
  has_next: boolean
  statuses: { id: string; label: string }[]
  staff: PipelineUser[]
  properties: PipelineProperty[]
  results: Quote[]
}
