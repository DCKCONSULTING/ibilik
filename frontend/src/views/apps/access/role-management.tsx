'use client'

import { useEffect, useMemo, useState } from 'react'

import { toast } from 'sonner'

import { useAuth } from '@/components/auth/auth-provider'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Field, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { isApiError } from '@/lib/api'
import { authApi } from '@/lib/auth/api'
import type { AppSection, PermissionDefinition, RoleDefinition } from '@/lib/auth/types'

const RoleManagement = () => {
  const { can } = useAuth()
  const [roles, setRoles] = useState<RoleDefinition[]>([])
  const [sections, setSections] = useState<AppSection[]>([])
  const [permissions, setPermissions] = useState<PermissionDefinition[]>([])
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState<RoleDefinition | null>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [isActive, setIsActive] = useState(true)
  const [allProperties, setAllProperties] = useState(false)
  const [manageLower, setManageLower] = useState(false)
  const [assignStaff, setAssignStaff] = useState(false)
  const [selected, setSelected] = useState<string[]>([])
  const [saving, setSaving] = useState(false)
  const canEdit = can('users.manage_roles')

  const load = () =>
    Promise.all([authApi.listRoles(), authApi.listPermissions().catch(() => ({ results: [] as PermissionDefinition[], sections: [] }))]).then(
      ([rolePayload, permissionPayload]) => {
        setRoles(rolePayload.results)
        setSections(rolePayload.sections ?? permissionPayload.sections ?? [])
        setPermissions(permissionPayload.results)
      }
    )

  useEffect(() => {
    load().catch(err => setError(isApiError(err) ? err.message : 'Unable to load roles.'))
  }, [])

  const groupedPermissions = useMemo(() => {
    return sections
      .map(section => ({
        ...section,
        items: permissions.filter(item => (item.section || item.module) === section.id)
      }))
      .filter(section => section.items.length > 0)
  }, [permissions, sections])

  const openEdit = (role: RoleDefinition) => {
    setEditing(role)
    setName(role.name)
    setDescription(role.description ?? '')
    setIsActive(role.is_active !== false)
    setAllProperties(Boolean(role.all_properties))
    setManageLower(Boolean(role.can_manage_lower_users))
    setAssignStaff(Boolean(role.can_assign_property_staff))
    setSelected(role.permissions)
  }

  const togglePermission = (codename: string, checked: boolean) => {
    setSelected(current => (checked ? [...current, codename] : current.filter(item => item !== codename)))
  }

  const save = async () => {
    if (!editing) return
    setSaving(true)

    try {
      await authApi.updateRole(editing.code, {
        name,
        description,
        is_active: isActive,
        all_properties: allProperties,
        can_manage_lower_users: manageLower,
        can_assign_property_staff: assignStaff,
        permissions: selected
      })
      await load()
      setEditing(null)
      toast.success('Role updated.')
    } catch (err) {
      toast.error(isApiError(err) ? err.message : 'Unable to update the role.')
    } finally {
      setSaving(false)
    }
  }

  const scopeLabel = (role: RoleDefinition) => {
    if (role.is_system_role) return 'Full system access'
    if (role.all_properties) return 'All properties'
    return 'Assigned properties'
  }

  return (
    <div className='flex flex-col gap-6'>
      <div>
        <h1 className='text-2xl font-semibold'>Roles</h1>
        <p className='text-muted-foreground text-sm'>
          System Admin is the Django superuser. Assign applications and permissions to roles here. Users inherit access from their role.
        </p>
      </div>

      {error && (
        <Alert variant='destructive'>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className='grid gap-4 md:grid-cols-2 xl:grid-cols-4'>
        {roles.map(role => (
          <Card key={role.code} className='shadow-none'>
            <CardHeader>
              <div className='flex items-start justify-between gap-2'>
                <CardTitle>{role.name}</CardTitle>
                {role.protected && <Badge>Protected</Badge>}
              </div>
              <CardDescription>{role.description || (role.is_system_role ? 'Protected system role' : 'Business role')}</CardDescription>
            </CardHeader>
            <CardContent className='space-y-3'>
              <div className='flex flex-wrap gap-2'>
                {role.level != null && <Badge variant='outline'>Level {role.level}</Badge>}
                <Badge variant='secondary'>{scopeLabel(role)}</Badge>
                {role.is_active === false && <Badge variant='outline'>Inactive</Badge>}
              </div>
              <p className='text-muted-foreground text-sm'>
                {role.is_system_role ? 'Unrestricted access' : `${role.permissions.length} app permissions`}
                {typeof role.user_count === 'number' ? ` · ${role.user_count} users` : ''}
              </p>
              {canEdit && !role.protected && (
                <Button size='sm' variant='outline' onClick={() => openEdit(role)}>
                  Edit permissions
                </Button>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <Dialog open={editing !== null} onOpenChange={open => !open && setEditing(null)}>
        <DialogContent className='max-h-[min(100dvh,44rem)] overflow-y-auto sm:max-w-2xl'>
          <DialogHeader>
            <DialogTitle>{editing?.name ?? 'Edit role'}</DialogTitle>
          </DialogHeader>
          {editing && (
            <div className='space-y-5'>
              <Field>
                <FieldLabel>Role name</FieldLabel>
                <Input value={name} onChange={event => setName(event.target.value)} />
              </Field>
              <Field>
                <FieldLabel>Description</FieldLabel>
                <Textarea value={description} onChange={event => setDescription(event.target.value)} />
              </Field>
              {editing.level != null && (
                <p className='text-muted-foreground text-sm'>Level {editing.level}</p>
              )}
              <div className='grid gap-3 sm:grid-cols-2'>
                <label className='flex items-center justify-between gap-3 text-sm'>
                  <span>Active</span>
                  <Switch checked={isActive} onCheckedChange={setIsActive} />
                </label>
                <label className='flex items-center justify-between gap-3 text-sm'>
                  <span>All properties</span>
                  <Switch checked={allProperties} onCheckedChange={setAllProperties} />
                </label>
                <label className='flex items-center justify-between gap-3 text-sm'>
                  <span>Manage lower-level users</span>
                  <Switch checked={manageLower} onCheckedChange={setManageLower} />
                </label>
                <label className='flex items-center justify-between gap-3 text-sm'>
                  <span>Assign property staff</span>
                  <Switch checked={assignStaff} onCheckedChange={setAssignStaff} />
                </label>
              </div>
              <div className='space-y-4'>
                <h3 className='text-sm font-medium'>App permissions</h3>
                {groupedPermissions.map(section => (
                  <div key={section.id} className='space-y-2'>
                    <p className='text-muted-foreground text-xs font-medium uppercase'>{section.name}</p>
                    <div className='space-y-2 rounded-md border p-3'>
                      {section.items.map(permission => (
                        <label key={permission.codename} className='flex items-start gap-2 text-sm'>
                          <Checkbox
                            checked={selected.includes(permission.codename)}
                            onCheckedChange={checked => togglePermission(permission.codename, checked === true)}
                          />
                          <span>
                            <span className='font-medium'>{permission.name}</span>
                          </span>
                        </label>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant='outline' onClick={() => setEditing(null)}>
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

export default RoleManagement
