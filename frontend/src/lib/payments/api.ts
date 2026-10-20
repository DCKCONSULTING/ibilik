import { api } from '@/lib/api'
import type { Payment, PaymentDraft, PaymentListResponse, PaymentRefund } from '@/lib/payments/types'

export const paymentsApi = {
  list(query?: Record<string, string | number | boolean | undefined>) {
    return api.get<PaymentListResponse>('/api/payments/', { query })
  },
  get(id: number) {
    return api.get<Payment>(`/api/payments/${id}/`)
  },
  create(payload: PaymentDraft) {
    return api.post<Payment>('/api/payments/', payload)
  },
  update(id: number, payload: Partial<Omit<PaymentDraft, 'case_id'>>) {
    return api.patch<Payment>(`/api/payments/${id}/`, payload)
  },
  cancel(id: number) {
    return api.delete<{ ok: boolean }>(`/api/payments/${id}/`)
  },
  submit(id: number) {
    return api.post<Payment>(`/api/payments/${id}/submit/`)
  },
  approve(id: number) {
    return api.post<Payment>(`/api/payments/${id}/approve/`)
  },
  reject(id: number, reason: string) {
    return api.post<Payment>(`/api/payments/${id}/reject/`, { rejection_reason: reason })
  },
  sendReminder(id: number, payload?: { channel?: string; content?: string }) {
    return api.post<{ ok: boolean; status: string; channel: string; payment: Payment }>(`/api/payments/${id}/remind/`, payload ?? {})
  },
  listAttachments(id: number) {
    return api.get<{ results: Payment['attachments'] }>(`/api/payments/${id}/attachments/`)
  },
  uploadAttachment(id: number, file: File, description = '') {
    const body = new FormData()

    body.append('file', file)
    if (description) body.append('description', description)

    return api.post<NonNullable<Payment['attachments']>[number]>(`/api/payments/${id}/attachments/`, body)
  },
  requestRefund(id: number, payload: { amount: string; reason?: string; complete?: boolean }) {
    return api.post<PaymentRefund>(`/api/payments/${id}/refund/`, payload)
  },
  listRefunds(query?: Record<string, string | number | boolean | undefined>) {
    return api.get<{ resource: string; count: number; results: PaymentRefund[] }>('/api/refunds/', { query })
  },
  getRefund(id: number) {
    return api.get<PaymentRefund>(`/api/refunds/${id}/`)
  },
  approveRefund(id: number) {
    return api.post<PaymentRefund>(`/api/refunds/${id}/approve/`)
  },
  rejectRefund(id: number, reason: string) {
    return api.post<PaymentRefund>(`/api/refunds/${id}/reject/`, { rejection_reason: reason })
  },
  completeRefund(id: number) {
    return api.post<PaymentRefund>(`/api/refunds/${id}/complete/`)
  },
  addCharge(paymentId: number, payload: Record<string, string | number | boolean | undefined>) {
    return api.post<Payment>(`/api/payments/${paymentId}/charges/`, payload)
  },
  addPenalty(paymentId: number, payload: Record<string, string | number | boolean | undefined>) {
    return api.post<Payment>(`/api/payments/${paymentId}/penalties/`, payload)
  },
  voidCharge(chargeId: number, reason: string) {
    return api.post<Payment>(`/api/charges/${chargeId}/void/`, { reason })
  }
}
