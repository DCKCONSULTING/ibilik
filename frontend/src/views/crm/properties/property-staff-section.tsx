'use client'

import { useEffect, useMemo, useState } from 'react'

import { toast } from 'sonner'

import { useAuth } from '@/components/auth/auth-provider'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Field, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { isApiError } from '@/lib/api'
import { authApi } from '@/lib/auth/api'
import type { ManagedUser, RoleDefinition } from '@/lib/auth/types'
import { propertiesApi } from '@/lib/properties/api'
import type { Property, PropertyStaff, PropertyStaffRole } from '@/lib/properties/types'

type PropertyStaffSectionProps = {
  property: Property
  canManage: boolean
  canViewUsers: boolean
  onUpdated: (property: Property) => void
}

type PickerOption = {
  id: string
  label: string
  description?: string
}

const initials = (name: string) =>
  name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map(part => part[0]?.toUpperCase())
    .join('') || '?'

const StaffAvatar = ({ name }: { name: string }) => (
  <Avatar size='sm'>
    <AvatarFallback>{initials(name)}</AvatarFallback>
  </Avatar>
)

const roleName = (role?: PropertyStaffRole | RoleDefinition | null) => role?.name || 'No role'

const SearchablePicker = ({
  value,
  options,
  placeholder,
  disabled,
  onChange
}: {
  value: string
  options: PickerOption[]
  placeholder: string
  disabled?: boolean
  onChange: (value: string) => void
}) => {
  const [query, setQuery] = useState('')
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()

    if (!needle) return options

    return options.filter(option => `${option.label} ${option.description ?? ''}`.toLowerCase().includes(needle))
  }, [options, query])

  return (
    <div className='space-y-2'>
      <Input
        value={query}
        disabled={disabled}
        placeholder={placeholder}
        onChange={event => setQuery(event.target.value)}
      />
      <div className='max-h-44 overflow-y-auto rounded-md border'>
        {filtered.length === 0 ? (
          <p className='text-muted-foreground px-3 py-2 text-sm'>No matches.</p>
        ) : (
          filtered.map(option => (
            <button
              key={option.id}
              type='button'
              disabled={disabled}
              className={`hover:bg-muted/50 flex w-full flex-col items-start px-3 py-2 text-left text-sm ${
                value === option.id ? 'bg-muted' : ''
              }`}
              onClick={() => onChange(option.id)}
            >
              <span className='font-medium'>{option.label}</span>
              {option.description && <span className='text-muted-foreground text-xs'>{option.description}</span>}
            </button>
          ))
        )}
      </div>
    </div>
  )
}

const TreeNode = ({
  node,
  depth = 0,
  onSelect
}: {
  node: PropertyStaff
  depth?: number
  onSelect: (member: PropertyStaff) => void
}) => (
  <div className={depth === 0 ? 'space-y-2' : 'border-border mt-2 space-y-2 border-l pl-4'}>
    <button
      type='button'
      className='hover:bg-muted/50 flex w-full items-start gap-3 rounded-md border px-3 py-2 text-left'
      onClick={() => onSelect(node)}
    >
      <StaffAvatar name={node.display_name} />
      <div className='min-w-0'>
        <p className='truncate text-sm font-medium'>{node.display_name}</p>
        <p className='text-muted-foreground truncate text-xs'>{roleName(node.role)}</p>
      </div>
      <Badge variant={node.is_active ? 'secondary' : 'outline'} className='ml-auto'>
        {node.is_active ? 'Active' : 'Inactive'}
      </Badge>
    </button>
    {node.reports?.map(child => (
      <TreeNode key={child.id} node={child} depth={depth + 1} onSelect={onSelect} />
    ))}
  </div>
)

const PropertyStaffSection = ({ property, canManage, canViewUsers, onUpdated }: PropertyStaffSectionProps) => {
  const { can } = useAuth()
  const [staff, setStaff] = useState<PropertyStaff[]>(property.staff ?? [])
  const [hierarchy, setHierarchy] = useState<PropertyStaff[]>([])
  const [roles, setRoles] = useState<PropertyStaffRole[]>([])
  const [users, setUsers] = useState<ManagedUser[]>([])
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState<PropertyStaff | null>(null)
  const [selected, setSelected] = useState<PropertyStaff | null>(null)
  const [userId, setUserId] = useState('')
  const [roleId, setRoleId] = useState('')
  const [managerId, setManagerId] = useState('none')
  const [saving, setSaving] = useState(false)
  const canLoadRoles = can(['users.view_user', 'users.manage_roles', 'properties.manage_staff'])

  const applyPayload = (payload: { results: PropertyStaff[]; roles?: PropertyStaffRole[]; hierarchy?: PropertyStaff[] }) => {
    setStaff(payload.results)
    setHierarchy(payload.hierarchy ?? [])
    if (payload.roles?.length) setRoles(payload.roles)
    onUpdated({ ...property, staff: payload.results, staff_count: payload.results.length })
  }

  const loadStaff = () =>
    propertiesApi.listStaff(property.id).then(payload => {
      applyPayload(payload)
      return payload
    })

  useEffect(() => {
    let mounted = true

    loadStaff().catch(() => {
      if (!mounted) return
      setStaff(property.staff ?? [])
    })

    return () => {
      mounted = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [property.id])

  useEffect(() => {
    if (!canLoadRoles) return

    authApi
      .listRoles()
      .then(payload => setRoles(payload.results))
      .catch(() => undefined)
  }, [canLoadRoles])

  useEffect(() => {
    if (!canViewUsers) return

    authApi
      .listUsers()
      .then(payload => setUsers(payload.results))
      .catch(() => setUsers([]))
  }, [canViewUsers])

  const assignableUsers = useMemo(() => {
    const assignedIds = new Set(staff.map(item => item.id))

    return users.filter(user => !assignedIds.has(user.id))
  }, [staff, users])

  const managerOptions = useMemo(
    () => staff.filter(item => !editing || item.id !== editing.id),
    [editing, staff]
  )

  const openCreate = () => {
    setEditing(null)
    setUserId('')
    setRoleId('')
    setManagerId('none')
    setDialogOpen(true)
  }

  const openEdit = (member: PropertyStaff) => {
    setEditing(member)
    setUserId(String(member.id))
    setRoleId(member.role?.id ?? '')
    setManagerId(member.reports_to?.id ? String(member.reports_to.id) : 'none')
    setDialogOpen(true)
    setSelected(null)
  }

  const save = async () => {
    setSaving(true)

    try {
      const reportsTo = managerId === 'none' ? null : Number(managerId)
      const payload = editing
        ? await propertiesApi.updateStaff(property.id, editing.id, {
            role: roleId || undefined,
            reports_to_id: reportsTo
          })
        : await propertiesApi.assignStaff(property.id, {
            user_id: Number(userId),
            role: roleId || undefined,
            reports_to_id: reportsTo
          })

      applyPayload(payload)
      setDialogOpen(false)
      toast.success(editing ? 'Staff assignment updated.' : 'Staff assigned.')
    } catch (error) {
      toast.error(isApiError(error) ? error.message : 'Unable to save the staff assignment.')
    } finally {
      setSaving(false)
    }
  }

  const removeStaff = async (member: PropertyStaff) => {
    setSaving(true)

    try {
      await propertiesApi.removeStaff(property.id, member.id)
      await loadStaff()
      setSelected(null)
      toast.success('Staff removed.')
    } catch (error) {
      toast.error(isApiError(error) ? error.message : 'Unable to remove staff.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className='space-y-6'>
      <div className='flex items-center justify-between gap-3'>
        <div>
          <h3 className='font-medium'>Staff</h3>
          <p className='text-muted-foreground text-sm'>
            Assigned people, roles from Roles, and reporting lines for this property.
          </p>
        </div>
        <div className='flex items-center gap-2'>
          {!canManage && <Badge variant='outline'>Read only</Badge>}
          {canManage && (
            <Button size='sm' onClick={openCreate}>
              Assign staff
            </Button>
          )}
        </div>
      </div>

      <div>
        <h4 className='mb-3 text-sm font-medium'>Reporting hierarchy</h4>
        {staff.length === 0 ? (
          <p className='text-muted-foreground text-sm'>No staff assigned to this property.</p>
        ) : hierarchy.length === 0 ? (
          <p className='text-muted-foreground text-sm'>Unable to build the reporting tree for this property.</p>
        ) : (
          <div className='space-y-3'>
            <p className='text-muted-foreground text-xs'>Unassigned / no manager</p>
            {hierarchy.map(node => (
              <TreeNode key={node.id} node={node} onSelect={setSelected} />
            ))}
          </div>
        )}
      </div>

      {staff.length > 0 && (
        <div className='space-y-2'>
          <h4 className='text-sm font-medium'>Staff list</h4>
          <ul className='space-y-2'>
            {staff.map(member => (
              <li key={member.id} className='flex items-center gap-2 rounded-md border px-3 py-2'>
                <button
                  type='button'
                  className='flex min-w-0 flex-1 items-center gap-3 text-left'
                  onClick={() => setSelected(member)}
                >
                  <StaffAvatar name={member.display_name} />
                  <div className='min-w-0'>
                    <p className='truncate text-sm font-medium'>{member.display_name}</p>
                    <p className='text-muted-foreground truncate text-xs'>
                      {roleName(member.role)}
                      {member.reports_to ? ` · Reports to ${member.reports_to.name}` : ' · No manager'}
                    </p>
                  </div>
                </button>
                <Badge variant={member.is_active ? 'secondary' : 'outline'}>{member.is_active ? 'Active' : 'Inactive'}</Badge>
                {canManage && (
                  <div className='flex shrink-0 gap-1'>
                    <Button size='sm' variant='outline' onClick={() => openEdit(member)}>
                      Edit
                    </Button>
                    <Button size='sm' variant='ghost' disabled={saving} onClick={() => void removeStaff(member)}>
                      Remove
                    </Button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className='sm:max-w-md'>
          <DialogHeader>
            <DialogTitle>{editing ? 'Edit staff assignment' : 'Assign staff'}</DialogTitle>
          </DialogHeader>
          <div className='space-y-4'>
            <Field>
              <FieldLabel>Staff member</FieldLabel>
              {editing ? (
                <p className='text-sm font-medium'>{editing.display_name}</p>
              ) : (
                <SearchablePicker
                  value={userId}
                  placeholder='Search people'
                  options={assignableUsers.map(user => ({
                    id: String(user.id),
                    label: user.display_name,
                    description: user.username
                  }))}
                  onChange={setUserId}
                />
              )}
            </Field>
            <Field>
              <FieldLabel>Role</FieldLabel>
              <SearchablePicker
                value={roleId}
                placeholder='Search roles'
                options={roles.map(role => ({
                  id: role.id,
                  label: role.name
                }))}
                onChange={setRoleId}
              />
            </Field>
            <Field>
              <FieldLabel>Reports to</FieldLabel>
              <SearchablePicker
                value={managerId}
                placeholder='Search managers'
                options={[
                  { id: 'none', label: 'No manager' },
                  ...managerOptions.map(member => ({
                    id: String(member.id),
                    label: member.display_name,
                    description: roleName(member.role)
                  }))
                ]}
                onChange={setManagerId}
              />
            </Field>
          </div>
          <DialogFooter>
            <Button variant='outline' onClick={() => setDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => void save()} disabled={saving || (!editing && !userId)}>
              {saving ? 'Saving…' : 'Save'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Sheet open={selected !== null} onOpenChange={open => !open && setSelected(null)}>
        <SheetContent className='overflow-y-auto sm:max-w-md'>
          <SheetHeader>
            <SheetTitle>{selected?.display_name ?? 'Staff'}</SheetTitle>
          </SheetHeader>
          {selected && (
            <div className='space-y-4 px-4 pb-6'>
              <div className='flex items-center gap-3'>
                <StaffAvatar name={selected.display_name} />
                <div>
                  <p className='font-medium'>{selected.display_name}</p>
                  <p className='text-muted-foreground text-sm'>{roleName(selected.role)}</p>
                </div>
              </div>
              <dl className='grid gap-3 text-sm'>
                <div>
                  <dt className='text-muted-foreground'>Reports to</dt>
                  <dd className='font-medium'>
                    {selected.reports_to
                      ? `${selected.reports_to.name}${selected.reports_to.role ? ` — ${selected.reports_to.role.name}` : ''}`
                      : 'No manager'}
                  </dd>
                </div>
                <div>
                  <dt className='text-muted-foreground'>Status</dt>
                  <dd className='font-medium'>{selected.is_active ? 'Active' : 'Inactive'}</dd>
                </div>
              </dl>
              {canManage && (
                <div className='flex flex-wrap gap-2'>
                  <Button variant='outline' onClick={() => openEdit(selected)}>
                    Edit
                  </Button>
                  <Button variant='ghost' disabled={saving} onClick={() => void removeStaff(selected)}>
                    Remove
                  </Button>
                </div>
              )}
            </div>
          )}
        </SheetContent>
      </Sheet>
    </section>
  )
}

export default PropertyStaffSection
