import { api } from '@/lib/api'
import type { DashboardResponse } from '@/lib/dashboard/types'

export const dashboardApi = {
  get(query?: Record<string, string | number | boolean | undefined>) {
    return api.get<DashboardResponse>('/api/dashboard/', { query })
  }
}
