import type { AssignedPropertySummary, ManagedUser, PermissionDefinition, RoleDefinition } from '@/lib/auth/types'

export type UserWriteDraft = {
  username: string
  first_name: string
  last_name: string
  email: string
  role: string
  is_active: boolean
  password: string
  property_access: 'GLOBAL' | 'ASSIGNED'
  property_ids: number[]
  reports_to_id: number | null
}

export const emptyUserDraft = (): UserWriteDraft => ({
  username: '',
  first_name: '',
  last_name: '',
  email: '',
  role: 'STAFF',
  is_active: true,
  password: '',
  property_access: 'ASSIGNED',
  property_ids: [],
  reports_to_id: null
})

export const buildUserWritePayload = (
  draft: UserWriteDraft,
  { isCreating, includeRole }: { isCreating: boolean; includeRole: boolean }
): Record<string, unknown> => {
  const payload: Record<string, unknown> = {
    first_name: draft.first_name,
    last_name: draft.last_name,
    email: draft.email,
    is_active: draft.is_active,
    property_access: draft.property_access,
    property_ids: draft.property_access === 'ASSIGNED' ? draft.property_ids : [],
    reports_to_id: draft.reports_to_id
  }

  if (includeRole) payload.role = draft.role
  if (isCreating) {
    payload.username = draft.username
    payload.password = draft.password
  }

  return payload
}

export const inheritedPermissionsForRole = (
  roleCode: string | null | undefined,
  roles: RoleDefinition[]
): string[] => {
  if (!roleCode) return []
  const role = roles.find(item => item.code === roleCode || item.id === roleCode)

  return role?.permissions ?? []
}

const ACTION_LABELS: Record<string, string> = {
  view: 'View',
  add: 'Create',
  create: 'Create',
  change: 'Edit',
  edit: 'Edit',
  delete: 'Delete',
  manage: 'Manage',
  approve: 'Approve',
  cancel: 'Cancel',
  send: 'Send',
  assign: 'Assign',
  reassign: 'Reassign',
  unassign: 'Unassign',
  resolve: 'Resolve',
  verify: 'Verify',
  reject: 'Reject',
  refund: 'Refund',
  override: 'Override'
}

const moduleLabel = (module: string) => {
  const labels: Record<string, string> = {
    dashboard: 'Dashboard',
    customers: 'Customers',
    inbox: 'Inbox',
    opportunities: 'CRM Pipeline',
    cases: 'Follow-ups',
    calendar: 'Calendar',
    quotes: 'Quotes',
    bookings: 'Bookings',
    payments: 'Payments',
    match: 'Match',
    properties: 'Properties',
    availability: 'Availability',
    locations: 'Locations',
    reports: 'Reports',
    users: 'Users',
    settings: 'Settings'
  }

  return labels[module] ?? module.replaceAll('_', ' ').replace(/\b\w/g, char => char.toUpperCase())
}

const actionLabel = (codename: string, definition?: PermissionDefinition) => {
  const action = codename.split('.')[1] ?? ''
  const prefix = action.split('_')[0] ?? action

  if (ACTION_LABELS[prefix]) return ACTION_LABELS[prefix]
  if (definition?.name) {
    return definition.name.replace(/^Can /i, '').replace(/^View /i, 'View')
  }

  return action.replaceAll('_', ' ')
}

export type InheritedPermissionGroup = {
  module: string
  label: string
  actions: string[]
}

export const groupInheritedPermissions = (
  codenames: string[],
  definitions: PermissionDefinition[] = []
): InheritedPermissionGroup[] => {
  const byCodename = new Map(definitions.map(item => [item.codename, item]))
  const grouped = new Map<string, string[]>()

  for (const codename of codenames) {
    const definition = byCodename.get(codename)
    const module = definition?.module ?? codename.split('.')[0] ?? 'other'
    const actions = grouped.get(module) ?? []
    const label = actionLabel(codename, definition)

    if (!actions.includes(label)) actions.push(label)
    grouped.set(module, actions)
  }

  return [...grouped.entries()].map(([module, actions]) => ({
    module,
    label: moduleLabel(module),
    actions
  }))
}

export const inheritedPermissionSummary = (roleName: string | null | undefined) => {
  if (!roleName) return 'No role assigned'

  return `Inherited from ${roleName}`
}

export const assignedPropertyNames = (properties: AssignedPropertySummary[] | undefined) => {
  return properties?.map(item => item.name).filter(Boolean) ?? []
}

export const assignedPropertySummary = (properties: AssignedPropertySummary[] | undefined) => {
  const names = assignedPropertyNames(properties)

  if (names.length === 0) return 'No assigned properties'
  if (names.length <= 2) return names.join(', ')

  return `${names.length} Properties`
}

export const draftFromUser = (user: ManagedUser): UserWriteDraft => ({
  username: user.username,
  first_name: user.first_name,
  last_name: user.last_name,
  email: user.email,
  role: user.role ?? 'STAFF',
  is_active: user.is_active,
  password: '',
  property_access: user.is_superuser ? 'GLOBAL' : user.property_access,
  property_ids: user.property_ids ?? [],
  reports_to_id: user.reporting_managers?.[0]?.id ?? null
})
