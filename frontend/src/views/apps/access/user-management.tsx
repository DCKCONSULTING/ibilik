'use client'

import { useEffect, useMemo, useState } from 'react'

import { ChevronDownIcon, PlusIcon } from 'lucide-react'

import { useAuth } from '@/components/auth/auth-provider'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { isApiError } from '@/lib/api'
import { authApi } from '@/lib/auth/api'
import { propertyAccessLabel, roleLabel } from '@/lib/auth/permissions'
import {
  assignedPropertyNames,
  assignedPropertySummary,
  buildUserWritePayload,
  draftFromUser,
  emptyUserDraft,
  groupInheritedPermissions,
  inheritedPermissionSummary,
  inheritedPermissionsForRole,
  type UserWriteDraft
} from '@/lib/auth/user-form'
import type { ManagedUser, PermissionDefinition, RoleDefinition } from '@/lib/auth/types'
import { propertiesApi } from '@/lib/properties/api'
import type { Property } from '@/lib/properties/types'

const formatDate = (value: string | null) => {
  if (!value) return 'Never'

  return new Date(value).toLocaleString()
}

const UserManagement = () => {
  const { can, user: currentUser, refresh } = useAuth()
  const [users, setUsers] = useState<ManagedUser[]>([])
  const [roles, setRoles] = useState<RoleDefinition[]>([])
  const [permissions, setPermissions] = useState<PermissionDefinition[]>([])
  const [properties, setProperties] = useState<Property[]>([])
  const [error, setError] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [editing, setEditing] = useState<ManagedUser | null>(null)
  const [isCreating, setIsCreating] = useState(false)
  const [propertyMenuOpen, setPropertyMenuOpen] = useState(false)
  const [draft, setDraft] = useState<UserWriteDraft>(emptyUserDraft())

  const canManageUsers = can('users.manage_user')
  const canManageRoles = can('users.manage_roles')
  const canAssignRoles = canManageRoles || canManageUsers

  const load = async () => {
    try {
      const [userPayload, rolePayload, permissionPayload, propertyPayload] = await Promise.all([
        authApi.listUsers(),
        authApi.listRoles().catch(() => ({ results: [] as RoleDefinition[] })),
        authApi.listPermissions().catch(() => ({ results: [] as PermissionDefinition[] })),
        propertiesApi.list().catch(() => ({ results: [] as Property[] }))
      ])

      setUsers(userPayload.results)
      setRoles(rolePayload.results)
      setPermissions(permissionPayload.results)
      setProperties(propertyPayload.results)
      setError(null)
    } catch (err) {
      setError(isApiError(err) ? err.message : 'Unable to load users.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const assignableRoles = useMemo(
    () => roles.filter(role => role.assignable !== false && (canManageRoles || !role.is_system_role)),
    [canManageRoles, roles]
  )

  const selectedRole = useMemo(
    () => roles.find(role => role.code === draft.role || role.id === draft.role),
    [draft.role, roles]
  )

  const inheritedCodes = useMemo(
    () => inheritedPermissionsForRole(draft.role, roles),
    [draft.role, roles]
  )

  const inheritedGroups = useMemo(
    () => groupInheritedPermissions(inheritedCodes, permissions),
    [inheritedCodes, permissions]
  )

  const managerOptions = useMemo(() => {
    return users.filter(user => {
      if (editing && user.id === editing.id) return false
      if (!user.is_active) return false
      const level = user.authority_level ?? user.role_detail?.authority_level
      const selectedLevel = selectedRole?.level
      if (typeof level === 'number' && typeof selectedLevel === 'number' && level >= selectedLevel) return false
      if (draft.property_access === 'GLOBAL' || user.property_access === 'GLOBAL' || user.is_superuser) return true
      return draft.property_ids.some(id => user.property_ids.includes(id))
    })
  }, [draft.property_access, draft.property_ids, editing, selectedRole?.level, users])

  const openCreate = () => {
    setEditing(null)
    setIsCreating(true)
    setFormError(null)
    setPropertyMenuOpen(false)
    setDraft(emptyUserDraft())
  }

  const openEdit = (user: ManagedUser) => {
    setIsCreating(false)
    setFormError(null)
    setEditing(user)
    setDraft(draftFromUser(user))
  }

  const closeModal = () => {
    setIsCreating(false)
    setEditing(null)
    setFormError(null)
    setPropertyMenuOpen(false)
    setDraft(emptyUserDraft())
  }

  const toggleProperty = (propertyId: number, checked: boolean) => {
    setDraft(current => ({
      ...current,
      property_access: 'ASSIGNED',
      property_ids: checked
        ? [...current.property_ids, propertyId]
        : current.property_ids.filter(item => item !== propertyId)
    }))
  }

  const selectedPropertyLabel = useMemo(() => {
    if (editing?.is_superuser || draft.property_access === 'GLOBAL') return 'All properties'

    const names = properties.filter(property => draft.property_ids.includes(property.id)).map(property => property.name)

    if (names.length === 0) return 'Select properties'
    if (names.length === 1) return names[0]

    return `${names.length} properties selected`
  }, [draft.property_access, draft.property_ids, editing?.is_superuser, properties])

  const save = async () => {
    setSaving(true)
    setFormError(null)

    try {
      const payload = buildUserWritePayload(draft, { isCreating, includeRole: canAssignRoles })

      if (isCreating) {
        await authApi.createUser(payload)
      } else if (editing) {
        await authApi.updateUser(editing.id, payload)

        if (draft.password) {
          await authApi.setPassword(editing.id, draft.password)
        }

        if (currentUser?.id === editing.id) {
          await refresh()
        }
      }

      closeModal()
      await load()
    } catch (err) {
      setFormError(isApiError(err) ? err.message : 'Unable to save the user.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className='flex flex-col gap-6'>
      <div className='flex flex-wrap items-center justify-between gap-3'>
        <div>
          <h1 className='text-2xl font-semibold'>Users</h1>
          <p className='text-muted-foreground text-sm'>
            Select a role when creating or editing a user. Permissions are inherited from the selected role.
          </p>
        </div>
        {canManageUsers && (
          <Button onClick={openCreate}>
            <PlusIcon />
            Create user
          </Button>
        )}
      </div>

      {error && (
        <Alert variant='destructive'>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Card className='shadow-none'>
        <CardHeader>
          <CardTitle>Directory</CardTitle>
          <CardDescription>Users inherit permissions from their role. Permissions cannot be assigned directly to a user.</CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className='text-muted-foreground text-sm'>Loading users…</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>User</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Properties</TableHead>
                  <TableHead>Reporting manager</TableHead>
                  <TableHead>Permissions</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Last login</TableHead>
                  {canManageUsers && <TableHead className='text-right'>Actions</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.map(user => {
                  const propertyNames = assignedPropertyNames(user.assigned_properties)
                  const managers = user.reporting_managers ?? []

                  return (
                    <TableRow key={user.id}>
                      <TableCell>
                        <div className='font-medium'>{user.display_name}</div>
                        <div className='text-muted-foreground text-xs'>@{user.username}</div>
                        {user.email ? <div className='text-muted-foreground text-xs'>{user.email}</div> : null}
                      </TableCell>
                      <TableCell>
                        <div className='flex flex-col gap-1'>
                          <Badge variant='secondary'>{user.role_name || roleLabel(user.role)}</Badge>
                          {typeof user.authority_level === 'number' ? (
                            <span className='text-muted-foreground text-xs'>Level {user.authority_level}</span>
                          ) : null}
                        </div>
                      </TableCell>
                      <TableCell className='max-w-56'>
                        {user.is_superuser || user.property_access === 'GLOBAL' ? (
                          <span className='text-sm'>{propertyAccessLabel(user)}</span>
                        ) : propertyNames.length > 2 ? (
                          <Popover>
                            <PopoverTrigger
                              render={<Button type='button' variant='ghost' className='h-auto px-0 font-normal' />}
                            >
                              {assignedPropertySummary(user.assigned_properties)}
                            </PopoverTrigger>
                            <PopoverContent align='start' className='w-64 text-sm'>
                              {propertyNames.join(', ')}
                            </PopoverContent>
                          </Popover>
                        ) : (
                          <span className='text-sm'>{assignedPropertySummary(user.assigned_properties)}</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <span className='text-sm'>
                          {managers.length === 0 ? '—' : managers.map(item => item.name).join(', ')}
                        </span>
                      </TableCell>
                      <TableCell>
                        <span className='text-sm'>{inheritedPermissionSummary(user.role_name || roleLabel(user.role))}</span>
                      </TableCell>
                      <TableCell>
                        <Badge variant={user.is_active ? 'default' : 'outline'}>
                          {user.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                      </TableCell>
                      <TableCell>{formatDate(user.last_login)}</TableCell>
                      {canManageUsers && (
                        <TableCell className='text-right'>
                          <Button variant='outline' size='sm' onClick={() => openEdit(user)}>
                            Edit
                          </Button>
                        </TableCell>
                      )}
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog
        open={isCreating || editing !== null}
        onOpenChange={open => {
          if (!open) closeModal()
        }}
      >
        <DialogContent className='max-h-[min(100dvh,40rem)] overflow-y-auto sm:max-w-lg'>
          <DialogHeader>
            <DialogTitle>{isCreating ? 'Create user' : 'Edit user'}</DialogTitle>
          </DialogHeader>
          {formError && (
            <Alert variant='destructive'>
              <AlertDescription>{formError}</AlertDescription>
            </Alert>
          )}
          <FieldGroup className='gap-4'>
            <Field>
              <FieldLabel htmlFor='manage-username'>Username</FieldLabel>
              <Input
                id='manage-username'
                value={draft.username}
                disabled={!isCreating}
                onChange={event => setDraft(current => ({ ...current, username: event.target.value }))}
              />
            </Field>
            <div className='grid gap-4 sm:grid-cols-2'>
              <Field>
                <FieldLabel htmlFor='manage-first-name'>First name</FieldLabel>
                <Input
                  id='manage-first-name'
                  value={draft.first_name}
                  onChange={event => setDraft(current => ({ ...current, first_name: event.target.value }))}
                />
              </Field>
              <Field>
                <FieldLabel htmlFor='manage-last-name'>Last name</FieldLabel>
                <Input
                  id='manage-last-name'
                  value={draft.last_name}
                  onChange={event => setDraft(current => ({ ...current, last_name: event.target.value }))}
                />
              </Field>
            </div>
            <Field>
              <FieldLabel htmlFor='manage-email'>Email</FieldLabel>
              <Input
                id='manage-email'
                type='email'
                value={draft.email}
                onChange={event => setDraft(current => ({ ...current, email: event.target.value }))}
              />
            </Field>
            {canAssignRoles && (
              <Field>
                <FieldLabel>Role</FieldLabel>
                <Select
                  value={draft.role}
                  onValueChange={value => {
                    if (!value) return
                    const nextRole = roles.find(role => role.code === value)
                    setDraft(current => ({
                      ...current,
                      role: value,
                      property_access: nextRole?.all_properties || value === 'SUPERUSER' ? 'GLOBAL' : current.property_access
                    }))
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder='Select a role' />
                  </SelectTrigger>
                  <SelectContent>
                    {assignableRoles.map(role => (
                      <SelectItem key={role.code} value={role.code}>
                        {role.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className='text-muted-foreground text-xs'>Permissions are inherited from the selected role.</p>
              </Field>
            )}
            <Field>
              <FieldLabel>Inherited permissions</FieldLabel>
              {selectedRole?.is_system_role || draft.role === 'SUPERUSER' ? (
                <p className='text-sm'>Full system access</p>
              ) : inheritedGroups.length === 0 ? (
                <p className='text-muted-foreground text-sm'>No permissions are assigned to this role.</p>
              ) : (
                <div className='bg-muted/40 max-h-48 space-y-2 overflow-y-auto rounded-md border p-3 text-sm'>
                  {inheritedGroups.map(group => (
                    <div key={group.module}>
                      <span className='font-medium'>{group.label}:</span> {group.actions.join(', ')}
                    </div>
                  ))}
                </div>
              )}
            </Field>
            <Field orientation='horizontal' className='items-center justify-between'>
              <FieldLabel htmlFor='manage-active'>Active</FieldLabel>
              <Switch
                id='manage-active'
                checked={draft.is_active}
                onCheckedChange={checked => setDraft(current => ({ ...current, is_active: checked }))}
              />
            </Field>
            {canManageUsers && (
              <Field>
                <FieldLabel>Assigned properties</FieldLabel>
                <Popover open={propertyMenuOpen} onOpenChange={setPropertyMenuOpen}>
                  <PopoverTrigger
                    disabled={editing?.is_superuser === true || selectedRole?.all_properties === true}
                    render={
                      <Button
                        type='button'
                        variant='outline'
                        className='w-full justify-between font-normal'
                        disabled={editing?.is_superuser === true || selectedRole?.all_properties === true}
                      />
                    }
                  >
                    <span className='truncate'>{selectedPropertyLabel}</span>
                    <ChevronDownIcon className='text-muted-foreground size-4 shrink-0' />
                  </PopoverTrigger>
                  <PopoverContent align='start' className='w-(--anchor-width) gap-0 p-1'>
                    {currentUser?.is_superuser && (
                      <label className='hover:bg-accent flex cursor-pointer items-start gap-2 rounded-sm px-2 py-1.5 text-sm'>
                        <Checkbox
                          checked={draft.property_access === 'GLOBAL'}
                          onCheckedChange={checked => {
                            setDraft(current => ({
                              ...current,
                              property_access: checked === true ? 'GLOBAL' : 'ASSIGNED',
                              property_ids: checked === true ? [] : current.property_ids
                            }))
                          }}
                        />
                        <span>
                          <span className='font-medium'>All properties</span>
                          <span className='text-muted-foreground block text-xs'>Access every current and future property</span>
                        </span>
                      </label>
                    )}
                    <div className='max-h-48 space-y-0.5 overflow-y-auto'>
                      {properties.length === 0 ? (
                        <p className='text-muted-foreground px-2 py-1.5 text-xs'>No properties available to assign.</p>
                      ) : (
                        properties.map(property => (
                          <label
                            key={property.id}
                            className='hover:bg-accent flex cursor-pointer items-start gap-2 rounded-sm px-2 py-1.5 text-sm'
                          >
                            <Checkbox
                              checked={draft.property_access === 'ASSIGNED' && draft.property_ids.includes(property.id)}
                              onCheckedChange={checked => toggleProperty(property.id, checked === true)}
                            />
                            <span>
                              <span className='font-medium'>{property.name}</span>
                              <span className='text-muted-foreground block text-xs'>
                                {property.city}, {property.region}
                              </span>
                            </span>
                          </label>
                        ))
                      )}
                    </div>
                  </PopoverContent>
                </Popover>
              </Field>
            )}
            {canManageUsers && (
              <Field>
                <FieldLabel>Reporting manager</FieldLabel>
                <Select
                  value={draft.reports_to_id == null ? 'none' : String(draft.reports_to_id)}
                  onValueChange={value => {
                    setDraft(current => ({
                      ...current,
                      reports_to_id: value === 'none' ? null : Number(value)
                    }))
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder='Select a reporting manager' />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value='none'>No reporting manager</SelectItem>
                    {managerOptions.map(user => (
                      <SelectItem key={user.id} value={String(user.id)}>
                        {user.display_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
            )}
            {canManageUsers && (
              <Field>
                <FieldLabel htmlFor='manage-password'>
                  {isCreating ? 'Password' : 'Reset password'}
                </FieldLabel>
                <Input
                  id='manage-password'
                  type='password'
                  value={draft.password}
                  autoComplete='new-password'
                  onChange={event => setDraft(current => ({ ...current, password: event.target.value }))}
                />
              </Field>
            )}
          </FieldGroup>
          <DialogFooter>
            <Button variant='outline' onClick={closeModal}>
              Cancel
            </Button>
            <Button onClick={() => void save()} disabled={saving}>
              {saving ? 'Saving…' : 'Save'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default UserManagement
