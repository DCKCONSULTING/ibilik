import type { PipelineLocation, PipelineProperty, PipelineStageDefinition, PipelineUser } from '@/lib/pipeline/types'

export type BookingStatus = 'upcoming' | 'in_house' | 'completed' | 'cancelled'

export type Booking = {
  id: number
  booking_number: string
  title: string
  status: BookingStatus | string
  status_label: string
  stage: string
  stage_label: string
  nights: number | null
  value: string | null
  value_label: string | null
  check_in: string | null
  check_out: string | null
  notes: string
  description?: string
  request?: string
  source?: string | null
  created_at: string | null
  updated_at: string | null
  case: {
    id: number
    case_number: string
    title: string
    stage: string
    stage_label: string
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
  location: PipelineLocation | null
  staff: PipelineUser | null
}

export type BookingListResponse = {
  resource: string
  count: number
  page: number
  page_size: number
  has_next: boolean
  statuses: { id: string; label: string }[]
  stages: PipelineStageDefinition[]
  staff: PipelineUser[]
  properties: PipelineProperty[]
  locations: PipelineLocation[]
  results: Booking[]
}
