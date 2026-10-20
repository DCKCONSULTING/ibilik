import assert from 'node:assert/strict'
import test from 'node:test'

const canAccess = (user, permission) => {
  if (!user) return false
  if (user.is_superuser) return true
  if (!permission) return true

  const required = Array.isArray(permission) ? permission : [permission]

  return required.some(item => user.permissions.includes(item))
}

const roleLabel = role => {
  if (!role) return 'No role'

  const labels = {
    SUPERUSER: 'System Admin',
    TOP_MANAGER: 'Top Manager',
    MANAGER: 'Manager',
    STAFF: 'Staff'
  }

  return labels[role] ?? role
}

const filterItem = (item, user) => {
  if (!canAccess(user, item.permission)) return null
  if (!item.childItems) return item

  const childItems = item.childItems.map(child => filterItem(child, user)).filter(Boolean)

  if (childItems.length === 0) return null

  return { ...item, childItems }
}

const filterNavItems = (items, user) =>
  items
    .map(group => ({
      ...group,
      items: group.items.map(item => filterItem(item, user)).filter(Boolean)
    }))
    .filter(group => group.items.length > 0)

const sampleNav = [
  {
    groupLabel: 'iBilik CRM',
    items: [
      { label: 'Dashboard', permission: 'dashboard.view_dashboard' },
      { label: 'Customers', permission: 'customers.view_customer' },
      { label: 'Inbox', permission: 'inbox.view_inbox' },
      { label: 'Properties', permission: 'properties.view_property' },
      { label: 'Bookings', permission: 'bookings.view_booking' },
      { label: 'Reports', permission: 'reports.view_report' }
    ]
  },
  {
    groupLabel: 'Administration',
    items: [
      { label: 'Users', permission: 'users.view_user' },
      { label: 'Roles', permission: 'users.manage_roles' },
      { label: 'Permissions', permission: 'users.manage_permissions' }
    ]
  }
]

const user = overrides => ({
  id: 1,
  username: 'staff.lee',
  role: 'STAFF',
  permissions: [],
  is_superuser: false,
  ...overrides
})

const navLabels = items => items.flatMap(group => group.items.map(item => item.label))

test('unauthenticated users cannot access CRM features', () => {
  assert.equal(canAccess(null, 'customers.view_customer'), false)
  assert.deepEqual(filterNavItems(sampleNav, null), [])
})

test('staff sees only permitted navigation', () => {
  const staff = user({
    permissions: ['customers.view_customer', 'inbox.view_inbox', 'bookings.view_booking']
  })
  const labels = navLabels(filterNavItems(sampleNav, staff))

  assert.deepEqual(labels, ['Customers', 'Inbox', 'Bookings'])
  assert.equal(labels.includes('Users'), false)
  assert.equal(labels.includes('Reports'), false)
  assert.equal(canAccess(staff, 'users.manage_user'), false)
})

test('manager sees manager navigation', () => {
  const manager = user({
    username: 'manager.pat',
    role: 'MANAGER',
    permissions: ['dashboard.view_dashboard', 'customers.view_customer', 'reports.view_report', 'users.view_user']
  })
  const labels = navLabels(filterNavItems(sampleNav, manager))

  assert.equal(labels.includes('Dashboard'), true)
  assert.equal(labels.includes('Reports'), true)
  assert.equal(labels.includes('Users'), true)
  assert.equal(labels.includes('Roles'), false)
  assert.equal(canAccess(manager, 'users.manage_user'), false)
})

test('superuser sees all navigation without enumerating permissions', () => {
  const superuser = user({
    username: 'root',
    role: 'SUPERUSER',
    permissions: [],
    is_superuser: true
  })
  const labels = navLabels(filterNavItems(sampleNav, superuser))

  assert.equal(canAccess(superuser, 'users.manage_permissions'), true)
  assert.equal(labels.includes('Dashboard'), true)
  assert.equal(labels.includes('Customers'), true)
  assert.equal(labels.includes('Users'), true)
  assert.equal(labels.includes('Roles'), true)
  assert.equal(labels.includes('Permissions'), true)
})

test('sidebar updates according to effective role permissions', () => {
  const staff = user({
    role: 'STAFF',
    permissions: ['dashboard.view_dashboard', 'customers.view_customer', 'bookings.view_booking']
  })
  const manager = user({
    username: 'manager.pat',
    role: 'MANAGER',
    permissions: [
      'dashboard.view_dashboard',
      'customers.view_customer',
      'bookings.view_booking',
      'reports.view_report',
      'users.view_user'
    ]
  })

  assert.equal(navLabels(filterNavItems(sampleNav, staff)).includes('Reports'), false)
  assert.equal(navLabels(filterNavItems(sampleNav, manager)).includes('Reports'), true)
  assert.equal(navLabels(filterNavItems(sampleNav, manager)).includes('Users'), true)
  assert.equal(navLabels(filterNavItems(sampleNav, manager)).includes('Roles'), false)
})

test('effective permissions come from the selected role rather than user overrides', () => {
  const staff = user({
    role: 'STAFF',
    permissions: ['customers.view_customer', 'bookings.view_booking']
  })

  assert.equal(canAccess(staff, 'quotes.approve_quote'), false)
  assert.equal(canAccess(staff, 'users.manage_user'), false)
  assert.equal(canAccess(staff, 'customers.view_customer'), true)
})

test('account property labels use names and organization-wide wording', () => {
  const accountPropertyNames = user => {
    if (user.is_superuser || user.property_access === 'GLOBAL' || user.property_scope_label === 'All authorized properties') {
      return []
    }

    const named = user.assigned_properties?.length ? user.assigned_properties : user.visible_properties

    return named?.map(item => item.name).filter(Boolean) ?? []
  }

  const accountPropertySummary = user => {
    if (user.is_superuser || user.property_access === 'GLOBAL' || user.property_scope_label === 'All authorized properties') {
      return 'All authorized properties'
    }

    const names = accountPropertyNames(user)

    if (names.length === 0) return 'No assigned properties'
    if (names.length <= 2) return names.join(', ')

    return `${names.length} Properties`
  }

  assert.equal(
    accountPropertySummary({ property_access: 'GLOBAL', is_superuser: false }),
    'All authorized properties'
  )
  assert.equal(
    accountPropertyNames({
      property_access: 'ASSIGNED',
      assigned_properties: [{ name: 'Kuala Lumpur City Centre' }]
    })[0],
    'Kuala Lumpur City Centre'
  )
  assert.equal(
    accountPropertySummary({
      property_access: 'ASSIGNED',
      assigned_properties: [{ name: 'A' }, { name: 'B' }, { name: 'C' }]
    }),
    '3 Properties'
  )
})

test('authorization is never based on username', () => {
  const namedAdmin = user({
    username: 'admin',
    role: 'STAFF',
    permissions: ['customers.view_customer']
  })

  assert.equal(canAccess(namedAdmin, 'users.manage_user'), false)
  assert.equal(roleLabel('STAFF'), 'Staff')
})
