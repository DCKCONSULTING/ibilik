import assert from 'node:assert/strict'
import test from 'node:test'

const RATE_PATTERN = /^-?\d+(\.\d+)?$/

const validatePropertyDraft = draft => {
  const errors = {}

  if (!draft.name.trim()) errors.name = 'Property name is required.'
  if (!draft.region.trim()) errors.region = 'Region is required.'
  if (!draft.city.trim()) errors.city = 'City is required.'

  const rate = draft.rate.trim()

  if (!rate) {
    errors.rate = 'Rate is required.'
  } else if (!RATE_PATTERN.test(rate) || !Number.isFinite(Number(rate))) {
    errors.rate = 'Rate must be a valid number.'
  } else if (Number(rate) < 0) {
    errors.rate = 'Rate cannot be negative.'
  }

  return errors
}

test('property form requires name, region, city, and rate', () => {
  const errors = validatePropertyDraft({ name: '', region: '', city: '', rate: '' })

  assert.equal(errors.name, 'Property name is required.')
  assert.equal(errors.region, 'Region is required.')
  assert.equal(errors.city, 'City is required.')
  assert.equal(errors.rate, 'Rate is required.')
})

test('property form rejects non-numeric rates', () => {
  const errors = validatePropertyDraft({
    name: 'iBilik Kuala Lumpur City Centre',
    region: 'Kuala Lumpur',
    city: 'Kuala Lumpur',
    rate: 'abc'
  })

  assert.equal(errors.rate, 'Rate must be a valid number.')
})

test('property form accepts a valid draft', () => {
  const errors = validatePropertyDraft({
    name: 'iBilik Kuala Lumpur City Centre',
    region: 'Kuala Lumpur',
    city: 'Kuala Lumpur',
    rate: '220.00'
  })

  assert.deepEqual(errors, {})
})
