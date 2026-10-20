import assert from 'node:assert/strict'
import test from 'node:test'

const emptyUserDraft = () => ({
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

const buildUserWritePayload = (draft, { isCreating, includeRole }) => {
  const payload = {
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

const inheritedPermissionsForRole = (roleCode, roles) => {
  const role = roles.find(item => item.code === roleCode || item.id === roleCode)

  return role?.permissions ?? []
}

const ACTION_LABELS = { view: 'View', create: 'Create', assign: 'Assign' }

const moduleLabel = module =>
  ({
    customers: 'Customers',
    bookings: 'Bookings',
    match: 'Match'
  })[module] ?? module

const actionLabel = codename => {
  const prefix = (codename.split('.')[1] ?? '').split('_')[0]

  return ACTION_LABELS[prefix] ?? prefix
}

const groupInheritedPermissions = (codenames, definitions = []) => {
  const byCodename = new Map(definitions.map(item => [item.codename, item]))
  const grouped = new Map()

  for (const codename of codenames) {
    const definition = byCodename.get(codename)
    const module = definition?.module ?? codename.split('.')[0]
    const actions = grouped.get(module) ?? []
    const label = actionLabel(codename)

    if (!actions.includes(label)) actions.push(label)
    grouped.set(module, actions)
  }

  return [...grouped.entries()].map(([module, actions]) => ({
    module,
    label: moduleLabel(module),
    actions
  }))
}

const inheritedPermissionSummary = roleName => `Inherited from ${roleName}`

const assignedPropertySummary = properties => {
  const names = properties?.map(item => item.name).filter(Boolean) ?? []

  if (names.length === 0) return 'No assigned properties'
  if (names.length <= 2) return names.join(', ')

  return `${names.length} Properties`
}

const draftFromUser = user => ({
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

test('user create form payload has a role selector and no editable permissions', () => {
  const created = buildUserWritePayload(
    {
      ...emptyUserDraft(),
      username: 'manager_kl',
      first_name: 'Aiman',
      last_name: 'Rahman',
      email: 'manager@example.com',
      role: 'MANAGER',
      property_ids: [2]
    },
    { isCreating: true, includeRole: true }
  )

  assert.equal(created.role, 'MANAGER')
  assert.equal('permissions' in created, false)
  assert.equal('individual_permissions' in created, false)
})

test('user edit form payload has a role selector and no editable permissions', () => {
  const edited = buildUserWritePayload(
    { ...emptyUserDraft(), role: 'STAFF', property_ids: [2] },
    { isCreating: false, includeRole: true }
  )

  assert.equal(edited.role, 'STAFF')
  assert.equal('permissions' in edited, false)
  assert.equal('individual_permissions' in edited, false)
})

test('inherited permissions are read-only groupings from the selected role', () => {
  const roles = [
    {
      code: 'MANAGER',
      permissions: ['customers.view_customer', 'bookings.view_booking', 'bookings.create_booking', 'match.assign_request']
    }
  ]
  const grouped = groupInheritedPermissions(inheritedPermissionsForRole('MANAGER', roles), [
    { codename: 'customers.view_customer', module: 'customers' },
    { codename: 'bookings.view_booking', module: 'bookings' },
    { codename: 'bookings.create_booking', module: 'bookings' },
    { codename: 'match.assign_request', module: 'match' }
  ])

  assert.equal(grouped.find(item => item.label === 'Customers').actions.join(', '), 'View')
  assert.equal(grouped.find(item => item.label === 'Bookings').actions.join(', '), 'View, Create')
  assert.equal(inheritedPermissionSummary('Manager'), 'Inherited from Manager')
})

test('role changes refresh the displayed inherited permissions', () => {
  const roles = [
    { code: 'STAFF', permissions: ['customers.view_customer'] },
    { code: 'MANAGER', permissions: ['customers.view_customer', 'reports.view_report'] }
  ]

  assert.deepEqual(inheritedPermissionsForRole('STAFF', roles), ['customers.view_customer'])
  assert.deepEqual(inheritedPermissionsForRole('MANAGER', roles), ['customers.view_customer', 'reports.view_report'])
})

test('property names display instead of ids', () => {
  assert.equal(assignedPropertySummary([{ id: 2, name: 'Kuala Lumpur City Centre' }]), 'Kuala Lumpur City Centre')
  assert.equal(
    assignedPropertySummary([
      { id: 2, name: 'Kuala Lumpur City Centre' },
      { id: 3, name: 'Penang Heritage Hotel' }
    ]),
    'Kuala Lumpur City Centre, Penang Heritage Hotel'
  )
  assert.equal(assignedPropertySummary([{ id: 1, name: 'A' }, { id: 2, name: 'B' }, { id: 3, name: 'C' }]), '3 Properties')
})

test('unauthorized role options are hidden when not assignable', () => {
  const assignable = [
    { code: 'SUPERUSER', assignable: false, is_system_role: true },
    { code: 'TOP_MANAGER', assignable: false },
    { code: 'STAFF', assignable: true }
  ].filter(role => role.assignable !== false)

  assert.deepEqual(
    assignable.map(role => role.code),
    ['STAFF']
  )
})

test('edit draft has a role and no writable permission list', () => {
  const draft = draftFromUser({
    username: 'manager_kl',
    first_name: 'Aiman',
    last_name: 'Rahman',
    email: 'manager@example.com',
    role: 'MANAGER',
    is_active: true,
    is_superuser: false,
    property_access: 'ASSIGNED',
    property_ids: [2],
    reporting_managers: [{ id: 4, name: 'Mina Top' }]
  })

  assert.equal(draft.role, 'MANAGER')
  assert.equal(draft.reports_to_id, 4)
  assert.equal('individual_permissions' in draft, false)
})
