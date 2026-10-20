import assert from 'node:assert/strict'
import test from 'node:test'

const hasGlobalPropertyAccess = user => {
  if (!user) return false
  if (user.is_superuser) return true

  return user.property_access === 'GLOBAL'
}

const canAccessPropertyId = (user, propertyId) => {
  if (!user) return false
  if (hasGlobalPropertyAccess(user)) return true

  return user.property_ids.includes(propertyId)
}

const defaultPropertyContext = (user, accessibleIds) => {
  if (!user) return null
  if (hasGlobalPropertyAccess(user)) return 'all'
  if (accessibleIds.length >= 1) return accessibleIds[0]

  return null
}

const propertyAccessLabel = user => {
  if (user.is_superuser || user.property_access === 'GLOBAL') return 'All Properties'

  const names = user.assigned_properties?.map(item => item.name) ?? []

  if (names.length === 0) return 'Assigned: none'

  return `Assigned: ${names.join(', ')}`
}

const user = overrides => ({
  id: 1,
  username: 'staff.lee',
  role: 'STAFF',
  permissions: ['properties.view_property'],
  is_superuser: false,
  property_access: 'ASSIGNED',
  property_ids: [1],
  assigned_properties: [{ id: 1, name: 'Hotel Cairo' }],
  ...overrides
})

test('superuser always has global property access', () => {
  const superuser = user({
    username: 'root',
    role: 'SUPERUSER',
    is_superuser: true,
    property_access: 'GLOBAL',
    property_ids: []
  })

  assert.equal(hasGlobalPropertyAccess(superuser), true)
  assert.equal(canAccessPropertyId(superuser, 99), true)
  assert.equal(defaultPropertyContext(superuser, [1, 2]), 'all')
  assert.equal(propertyAccessLabel(superuser), 'All Properties')
})

test('global staff sees all properties without becoming a manager', () => {
  const globalStaff = user({
    username: 'staff.global',
    property_access: 'GLOBAL',
    property_ids: [],
    assigned_properties: []
  })

  assert.equal(hasGlobalPropertyAccess(globalStaff), true)
  assert.equal(canAccessPropertyId(globalStaff, 2), true)
  assert.equal(globalStaff.role, 'STAFF')
  assert.equal(propertyAccessLabel(globalStaff), 'All Properties')
})

test('assigned staff only sees assigned properties', () => {
  const assigned = user({ property_ids: [1], assigned_properties: [{ id: 1, name: 'Hotel Cairo' }] })

  assert.equal(hasGlobalPropertyAccess(assigned), false)
  assert.equal(canAccessPropertyId(assigned, 1), true)
  assert.equal(canAccessPropertyId(assigned, 2), false)
  assert.equal(defaultPropertyContext(assigned, [1, 3]), 1)
  assert.equal(propertyAccessLabel(assigned), 'Assigned: Hotel Cairo')
})

test('assigned staff with one property defaults to that property', () => {
  const assigned = user({ property_ids: [4] })

  assert.equal(defaultPropertyContext(assigned, [4]), 4)
})

test('unauthorized users cannot access a property id from the client helpers', () => {
  assert.equal(canAccessPropertyId(null, 1), false)
  assert.equal(defaultPropertyContext(null, [1]), null)
})
