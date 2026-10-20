import type { AuthUser, ManagedUser, PropertyAccessMode } from './types'

export type PermissionKey = string | string[] | undefined

export type PermissibleItem = {
  permission?: PermissionKey
  childItems?: PermissibleItem[]
  [key: string]: unknown
}

export type PermissibleGroup = {
  items: PermissibleItem[]
  [key: string]: unknown
}

export const canAccess = (user: AuthUser | null | undefined, permission?: PermissionKey): boolean => {
  if (!user) return false
  if (user.is_superuser) return true
  if (!permission) return true

  const required = Array.isArray(permission) ? permission : [permission]

  return required.some(item => user.permissions.includes(item))
}

export const roleLabel = (role: string | null | undefined): string => {
  if (!role) return 'No role'

  const labels: Record<string, string> = {
    SUPERUSER: 'System Admin',
    TOP_MANAGER: 'Top Manager',
    MANAGER: 'Manager',
    STAFF: 'Staff'
  }

  return labels[role] ?? role.replaceAll('_', ' ')
}

const filterItem = <T extends PermissibleItem>(item: T, user: AuthUser | null): T | null => {
  if (!canAccess(user, item.permission)) return null

  if (!item.childItems) return item

  const childItems = item.childItems
    .map(child => filterItem(child, user))
    .filter((child): child is PermissibleItem => child !== null)

  if (childItems.length === 0) return null

  return { ...item, childItems }
}

export const hasGlobalPropertyAccess = (user: AuthUser | null | undefined): boolean => {
  if (!user) return false
  if (user.is_superuser) return true

  return user.property_access === 'GLOBAL'
}

export const canAccessPropertyId = (user: AuthUser | null | undefined, propertyId: number): boolean => {
  if (!user) return false
  if (hasGlobalPropertyAccess(user)) return true

  return user.property_ids.includes(propertyId)
}

export const propertyAccessLabel = (
  user: Pick<ManagedUser, 'is_superuser' | 'property_access' | 'assigned_properties'>
): string => {
  if (user.is_superuser || user.property_access === 'GLOBAL') return 'All Properties'

  const names = user.assigned_properties?.map(item => item.name) ?? []

  if (names.length === 0) return 'Assigned: none'

  return `Assigned: ${names.join(', ')}`
}

export const accountPropertyNames = (
  user: Pick<AuthUser, 'is_superuser' | 'property_access' | 'property_scope_label' | 'assigned_properties' | 'visible_properties'>
): string[] => {
  if (user.is_superuser || user.property_access === 'GLOBAL' || user.property_scope_label === 'All authorized properties') {
    return []
  }

  const named = user.assigned_properties?.length ? user.assigned_properties : user.visible_properties

  return named?.map(item => item.name).filter(Boolean) ?? []
}

export const accountPropertyHeading = (names: string[]) => (names.length === 1 ? 'Property' : 'Properties')

export const accountPropertySummary = (
  user: Pick<AuthUser, 'is_superuser' | 'property_access' | 'property_scope_label' | 'assigned_properties' | 'visible_properties'>
): string => {
  if (user.is_superuser || user.property_access === 'GLOBAL' || user.property_scope_label === 'All authorized properties') {
    return 'All authorized properties'
  }

  const names = accountPropertyNames(user)

  if (names.length === 0) return 'No assigned properties'
  if (names.length <= 2) return names.join(', ')

  return `${names.length} Properties`
}

export const defaultPropertyContext = (
  user: AuthUser | null | undefined,
  accessibleIds: number[]
): number | 'all' | null => {
  if (!user) return null
  if (hasGlobalPropertyAccess(user)) return 'all'
  if (accessibleIds.length === 1) return accessibleIds[0]
  if (accessibleIds.length > 1) return accessibleIds[0]

  return null
}

export const isPropertyAccessMode = (value: string): value is PropertyAccessMode => {
  return value === 'GLOBAL' || value === 'ASSIGNED'
}

export const filterNavItems = <T extends PermissibleGroup>(items: T[], user: AuthUser | null): T[] => {
  return items
    .map(group => {
      const groupItems = group.items
        .map(item => filterItem(item, user))
        .filter((item): item is PermissibleItem => item !== null)

      return { ...group, items: groupItems }
    })
    .filter(group => group.items.length > 0)
}
