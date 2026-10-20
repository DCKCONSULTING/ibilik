import type { PipelineProperty, PipelineStageDefinition, PipelineUser } from '@/lib/pipeline/types'

export type PaymentTypeId = 'deposit' | 'payment'
export type PaymentMethodId = 'cash' | 'bank_transfer' | 'credit_card' | 'debit_card' | 'online' | 'other'
export type PaymentWorkflowStatus =
  | 'pending'
  | 'proof_submitted'
  | 'pending_approval'
  | 'approved'
  | 'rejected'
  | 'cancelled'
export type PaymentDisplayStatus = PaymentWorkflowStatus | 'overdue'
export type RefundStatusId = 'requested' | 'pending_approval' | 'approved' | 'rejected' | 'completed' | 'cancelled'

export type PaymentUser = PipelineUser

export type PaymentCase = {
  id: number
  case_number: string
  title: string
  stage: string
  stage_label: string
  source: string | null
  source_label: string | null
  value: string | null
}

export type PaymentCustomer = {
  id: number
  name: string
  email: string
  phone: string
}

export type PaymentAttachment = {
  id: number
  original_name: string
  content_type: string
  description: string
  is_image: boolean
  uploaded_by: PaymentUser | null
  uploaded_at: string | null
  url: string
}

export type PaymentRefund = {
  id: number
  refund_number: string
  payment_id: number
  amount: string
  amount_label: string | null
  reason: string
  status: RefundStatusId | string
  status_label: string
  requested_by: PaymentUser | null
  requested_at: string | null
  approved_by: PaymentUser | null
  approved_at: string | null
  rejected_by: PaymentUser | null
  rejected_at: string | null
  rejection_reason: string
  completed_by: PaymentUser | null
  completed_at: string | null
}

export type PaymentBalance = {
  case_value: string | null
  room_charges?: string | null
  extra_charges?: string | null
  penalties?: string | null
  taxes?: string | null
  discounts?: string | null
  adjustments?: string | null
  total_charges?: string | null
  paid: string | null
  deposits: string | null
  refunded: string | null
  pending_refunds?: string | null
  outstanding: string | null
  account_status?: string
  account_status_label?: string
}

export type PaymentLedgerRow = {
  id: string
  source: string
  source_id: number
  type: string
  type_label: string
  description: string
  amount: string | null
  signed_amount: string | null
  method: string
  method_label: string
  status: string
  status_label: string
  reference: string
  notes: string
  reason: string
  created_by: PaymentUser | null
  occurred_at: string | null
  voidable: boolean
}

export type PaymentCharge = {
  id: number
  kind: string
  kind_label: string
  category: string
  category_label: string
  description: string
  quantity: string | null
  unit_price: string | null
  tax_amount: string | null
  amount: string | null
  amount_label: string | null
  currency: string
  reason: string
  notes: string
  status: string
  status_label: string
  occurred_at: string | null
  created_by: PaymentUser | null
  voided_by: PaymentUser | null
  voided_at: string | null
  void_reason: string
  created_at: string | null
}

export type Payment = {
  id: number
  payment_number: string
  payment_type: PaymentTypeId | string
  payment_type_label: string
  amount: string
  amount_label: string | null
  currency: string
  payment_method: PaymentMethodId | string
  payment_method_label: string
  workflow_status: PaymentWorkflowStatus | string
  status: PaymentDisplayStatus | string
  status_label: string
  is_overdue: boolean
  expected_date: string | null
  paid_at: string | null
  notes: string
  created_by: PaymentUser | null
  approved_by: PaymentUser | null
  approved_at: string | null
  rejected_by: PaymentUser | null
  rejected_at: string | null
  rejection_reason: string
  submitted_at: string | null
  created_at: string | null
  updated_at: string | null
  refundable_amount: string | null
  attachment_count: number
  case: PaymentCase
  customer: PaymentCustomer
  property: PipelineProperty | null
  staff: PaymentUser | null
  attachments?: PaymentAttachment[]
  refunds?: PaymentRefund[]
  charges?: PaymentCharge[]
  ledger?: PaymentLedgerRow[]
  balance?: PaymentBalance
  balance_labels?: Record<string, string | null>
  reply_channels?: string[]
  location?: { id: number; name: string; code: string } | null
  check_in?: string | null
  check_out?: string | null
}

export type PaymentSummary = {
  expected: string
  pending_approval: string
  approved: string
  deposits: string
  refunded: string
  expected_label?: string | null
  pending_approval_label?: string | null
  approved_label?: string | null
  deposits_label?: string | null
  refunded_label?: string | null
}

export type PaymentListResponse = {
  resource: string
  count: number
  page: number
  page_size: number
  has_next: boolean
  summary: PaymentSummary
  types: { id: string; label: string }[]
  methods: { id: string; label: string }[]
  statuses: { id: string; label: string }[]
  stages: PipelineStageDefinition[]
  sources: { id: string; label: string }[]
  staff: PaymentUser[]
  properties: PipelineProperty[]
  results: Payment[]
  balance?: PaymentBalance
  balance_labels?: Record<keyof PaymentBalance, string | null>
}

export type PaymentDraft = {
  case_id: number
  payment_type?: PaymentTypeId | string
  amount: string
  currency?: string
  payment_method?: PaymentMethodId | string
  expected_date?: string | null
  paid_at?: string | null
  notes?: string
  received?: boolean
  idempotency_key?: string
}

export const workflowStatus = (payment: Payment) => payment.workflow_status || payment.status
