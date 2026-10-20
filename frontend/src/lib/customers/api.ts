import { api } from '@/lib/api'
import type { Customer, CustomerDraft, CustomerListResponse } from '@/lib/customers/types'

export const customersApi = {
  list(query?: Record<string, string | number | boolean | undefined>) {
    return api.get<CustomerListResponse>('/api/customers/', { query })
  },
  get(id: number) {
    return api.get<Customer>(`/api/customers/${id}/`)
  },
  create(payload: Omit<CustomerDraft, 'property_id'> & { property_id?: number }) {
    return api.post<Customer>('/api/customers/', payload)
  },
  update(id: number, payload: Partial<CustomerDraft> & { property_id?: number }) {
    return api.patch<Customer>(`/api/customers/${id}/`, payload)
  }
}
