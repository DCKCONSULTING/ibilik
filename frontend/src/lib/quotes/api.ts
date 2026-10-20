import { api } from '@/lib/api'
import type { Quote, QuoteListResponse } from '@/lib/quotes/types'

export const quotesApi = {
  list(query?: Record<string, string | number | boolean | undefined>) {
    return api.get<QuoteListResponse>('/api/quotes/', { query })
  },
  get(id: number) {
    return api.get<Quote>(`/api/quotes/${id}/`)
  }
}
