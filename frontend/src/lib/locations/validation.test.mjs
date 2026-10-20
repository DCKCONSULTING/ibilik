import assert from 'node:assert/strict'
import test from 'node:test'

const CAPACITY_PATTERN = /^\d+$/

const validateLocationDraft = draft => {
  const errors = {}

  if (!draft.name.trim()) errors.name = 'Location name is required.'
  if (!draft.type) errors.type = 'Type is required.'

  const capacity = draft.capacity.trim()

  if (capacity) {
    if (!CAPACITY_PATTERN.test(capacity) || Number(capacity) < 1) {
      errors.capacity = 'Capacity must be a positive integer.'
    }
  }

  return errors
}

test('location form requires name and type', () => {
  const errors = validateLocationDraft({
    name: '',
    code: '',
    type: '',
    capacity: '',
    description: '',
    status: 'available',
    active: true
  })

  assert.equal(errors.name, 'Location name is required.')
  assert.equal(errors.type, 'Type is required.')
})

test('location form rejects invalid capacity', () => {
  const errors = validateLocationDraft({
    name: 'Room 101',
    code: '101',
    type: 'room',
    capacity: '0',
    description: '',
    status: 'available',
    active: true
  })

  assert.equal(errors.capacity, 'Capacity must be a positive integer.')
})

test('location form accepts room, table, meeting room, villa, suite, and other drafts', () => {
  for (const type of ['room', 'table', 'meeting_room', 'villa', 'suite', 'other']) {
    const errors = validateLocationDraft({
      name: 'Resource 01',
      code: '01',
      type,
      capacity: '4',
      description: '',
      status: 'available',
      active: true
    })

    assert.deepEqual(errors, {})
  }
})
