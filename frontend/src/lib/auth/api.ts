import { api } from '@/lib/api'
import type { AuthUser, LoginResponse, ManagedUser, PermissionDefinition, RoleDefinition, RoleListResponse } from '@/lib/auth/types'

export const authApi = {
  csrf() {
    return api.get<{ csrfToken: string }>('/api/auth/csrf/')
  },
  login(username: string, password: string) {
    return api.post<LoginResponse>('/api/auth/login/', { username, password })
  },
  logout() {
    return api.post<{ ok: boolean }>('/api/auth/logout/')
  },
  me() {
    return api.get<AuthUser>('/api/auth/me/')
  },
  updateMe(payload: Record<string, unknown>) {
    return api.patch<AuthUser>('/api/auth/me/', payload)
  },
  changePassword(payload: { current_password: string; password: string }) {
    return api.post<{ ok: boolean }>('/api/auth/password/', payload)
  },
  deactivateAccount() {
    return api.post<{ ok: boolean }>('/api/auth/deactivate/')
  },
  listUsers() {
    return api.get<{ results: ManagedUser[] }>('/api/users/')
  },
  getUser(id: number) {
    return api.get<ManagedUser>(`/api/users/${id}/`)
  },
  createUser(payload: Record<string, unknown>) {
    return api.post<ManagedUser>('/api/users/', payload)
  },
  updateUser(id: number, payload: Record<string, unknown>) {
    return api.patch<ManagedUser>(`/api/users/${id}/`, payload)
  },
  setPassword(id: number, password: string) {
    return api.post<{ ok: boolean }>(`/api/users/${id}/password/`, { password })
  },
  listRoles() {
    return api.get<RoleListResponse>('/api/roles/')
  },
  updateRole(code: string, payload: Record<string, unknown>) {
    return api.patch<RoleDefinition>(`/api/roles/${code}/`, payload)
  },
  createRole(payload: Record<string, unknown>) {
    return api.post<RoleDefinition>('/api/roles/', payload)
  },
  listPermissions() {
    return api.get<{ results: PermissionDefinition[]; sections?: { id: string; name: string }[] }>('/api/permissions/')
  }
}
