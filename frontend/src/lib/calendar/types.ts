import type { PipelineProperty, PipelineStageDefinition, PipelineUser } from '@/lib/pipeline/types'

export type CalendarEventType = 'check_in' | 'check_out' | 'follow_up' | 'payment' | 'quote' | 'approval' | 'finance'

export type CalendarEventCase = {
  id: number
  case_number: string
  title: string
  stage: string
  stage_label: string
  source: string | null
  source_label: string | null
}

export type CalendarEventCustomer = {
  id: number
  name: string
  email: string
  phone: string
}

export type CalendarApiEvent = {
  id: string
  type: CalendarEventType | string
  type_label: string
  title: string
  start: string
  end: string
  all_day: boolean
  status: string | null
  status_label: string | null
  source_model: string
  source_id: number
  case_id: number
  case: CalendarEventCase
  customer: CalendarEventCustomer
  property: PipelineProperty | null
  staff: PipelineUser | null
  metadata: Record<string, string | number | null | undefined>
}

export type CalendarEventsResponse = {
  resource: string
  count: number
  start: string
  end: string
  types: { id: string; label: string }[]
  stages: PipelineStageDefinition[]
  sources: { id: string; label: string }[]
  staff: PipelineUser[]
  properties: PipelineProperty[]
  results: CalendarApiEvent[]
}
