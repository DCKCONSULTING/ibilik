import type { Booking } from '@/lib/bookings/types'
import type { CaseFollowUp, PipelineProperty } from '@/lib/pipeline/types'

export type DashboardMoney = string | null

export type DashboardKpis = {
  check_ins_today: number
  check_outs_today: number
  in_house: number
  upcoming: number
  occupancy_rate: number
  occupied_rooms: number
  bookable_rooms: number
  open_pipeline: number
  pipeline_value: DashboardMoney
  pipeline_value_label: string | null
  pending_payments: number
  pending_amount: DashboardMoney
  pending_amount_label: string | null
  overdue_payments: number
  overdue_amount: DashboardMoney
  overdue_amount_label: string | null
  open_follow_ups: number
  overdue_follow_ups: number
  rooms_attention: number
  open_maintenance: number
  customers: number
  revenue_this_month: DashboardMoney
  revenue_this_month_label: string | null
}

export type DashboardStage = {
  id: string
  label: string
  count: number
  value: DashboardMoney
  value_label: string | null
}

export type DashboardRoomStatus = {
  id: string
  label: string
  count: number
}

export type DashboardRoom = {
  id: number
  name: string
  code: string
  type: string
  type_label: string
  status: string
  status_label: string
  occupancy: string
  occupancy_label: string
  property: PipelineProperty | null
}

export type DashboardPayment = {
  id: number
  payment_number: string
  payment_type: string
  payment_type_label: string
  amount: DashboardMoney
  amount_label: string | null
  currency: string
  status: string
  status_label: string
  is_overdue: boolean
  expected_date: string | null
  case: {
    id: number
    case_number: string
    title: string
  }
  customer: {
    id: number
    name: string
    email: string
    phone: string
  }
  property: PipelineProperty | null
  location: { id: number; name: string; code: string } | null
}

export type DashboardResponse = {
  resource: string
  generated_at: string | null
  kpis: DashboardKpis
  rooms: {
    total: number
    bookable: number
    occupied: number
    occupancy_rate: number
    by_status: DashboardRoomStatus[]
    attention: DashboardRoom[]
  }
  pipeline: {
    open_count: number
    open_value: DashboardMoney
    open_value_label: string | null
    by_stage: DashboardStage[]
  }
  arrivals: Booking[]
  departures: Booking[]
  in_house: Booking[]
  recent_bookings: Booking[]
  pending_payments: DashboardPayment[]
  follow_ups: CaseFollowUp[]
  properties: PipelineProperty[]
}
