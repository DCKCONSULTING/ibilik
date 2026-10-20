export type AppRole = 'SUPERUSER' | 'TOP_MANAGER' | 'MANAGER' | 'STAFF' | string

export type PropertyAccessMode = 'GLOBAL' | 'ASSIGNED'

export type AssignedPropertySummary = {
  id: number
  name: string
}

export type ReportingManagerSummary = {
  id: number
  name: string
  username?: string
}

export type AuthUser = {
  id: number
  username: string
  first_name: string
  last_name: string
  display_name: string
  email: string
  role: AppRole | null
  role_name?: string
  authority_level?: number | null
  permissions: string[]
  effective_permissions?: string[]
  is_active: boolean
  is_staff: boolean
  is_superuser: boolean
  date_joined: string | null
  last_login: string | null
  individual_permissions?: string[]
  property_access: PropertyAccessMode
  property_ids: number[]
  assigned_properties?: AssignedPropertySummary[]
  reporting_managers?: ReportingManagerSummary[]
  visible_properties?: AssignedPropertySummary[]
  property_scope?: 'all_authorized' | 'assigned' | string
  property_scope_label?: string | null
}

export type ManagedUser = AuthUser & {
  individual_permissions: string[]
  assigned_properties: AssignedPropertySummary[]
  reporting_managers?: ReportingManagerSummary[]
  role_detail?: {
    id: string | null
    code: string | null
    name?: string | null
    authority_level?: number | null
    all_properties?: boolean
  }
  permissions_source?: string
}

export type AppSection = {
  id: string
  name: string
}

export type RoleDefinition = {
  id: string
  name: string
  code: string
  description?: string
  level?: number | null
  parent?: string | null
  permissions: string[]
  is_system_role: boolean
  is_builtin?: boolean
  is_active?: boolean
  protected?: boolean
  all_properties?: boolean
  can_manage_lower_users?: boolean
  can_assign_property_staff?: boolean
  user_count?: number
  assignable?: boolean
}

export type PermissionDefinition = {
  codename: string
  name: string
  module: string
  section?: string
}

export type RoleListResponse = {
  results: RoleDefinition[]
  sections?: AppSection[]
}

export type LoginResponse = {
  user: AuthUser
}
