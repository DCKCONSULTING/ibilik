import assert from 'node:assert/strict'
import test from 'node:test'

const PIPELINE_STAGES = [
  { id: 'new', label: 'New' },
  { id: 'qualified', label: 'Qualified' },
  { id: 'quoted', label: 'Quoted' },
  { id: 'negotiating', label: 'Negotiating' },
  { id: 'won', label: 'Won' },
  { id: 'lost', label: 'Lost' }
]

const groupByStage = opportunities => {
  const grouped = Object.fromEntries(PIPELINE_STAGES.map(stage => [stage.id, []]))

  for (const opportunity of opportunities) {
    grouped[opportunity.stage].push(opportunity)
  }

  return grouped
}

test('pipeline stages use the canonical CRM labels and order', () => {
  assert.deepEqual(
    PIPELINE_STAGES.map(stage => stage.label),
    ['New', 'Qualified', 'Quoted', 'Negotiating', 'Won', 'Lost']
  )
})

test('pipeline cards use assigned staff names and keep Unassigned when none is set', () => {
  const staffName = opportunity =>
    opportunity.assigned_user?.name || opportunity.assigned_to?.display_name || null

  assert.equal(
    staffName({
      assigned_user: { id: 15, name: 'Ahmed Hassan', display_name: 'Ahmed Hassan' },
      assigned_to: { id: 15, display_name: 'Ahmed Hassan' }
    }),
    'Ahmed Hassan'
  )
  assert.equal(staffName({ assigned_user: null, assigned_to: null }), null)
})

test('pipeline cards stay in the stage returned by the API', () => {
  const grouped = groupByStage([
    { id: 1, stage: 'new', customer: { name: 'John Smith' } },
    { id: 2, stage: 'qualified', customer: { name: 'Sarah Ahmed' } },
    { id: 3, stage: 'quoted', customer: { name: 'Mohamed Ali' } },
    { id: 4, stage: 'negotiating', customer: { name: 'Emma Wilson' } },
    { id: 5, stage: 'won', customer: { name: 'David Miller' } },
    { id: 6, stage: 'lost', customer: { name: 'Nour Khaled' } }
  ])

  assert.equal(grouped.new[0].customer.name, 'John Smith')
  assert.equal(grouped.qualified[0].customer.name, 'Sarah Ahmed')
  assert.equal(grouped.quoted[0].customer.name, 'Mohamed Ali')
  assert.equal(grouped.negotiating[0].customer.name, 'Emma Wilson')
  assert.equal(grouped.won[0].customer.name, 'David Miller')
  assert.equal(grouped.lost[0].customer.name, 'Nour Khaled')
})
