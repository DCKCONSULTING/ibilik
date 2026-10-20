import type { Opportunity, OpportunityDraft, PipelineStage, WorkflowAction } from '@/lib/pipeline/types'

export const emptyOpportunityDraft = (): OpportunityDraft => ({
  title: '',
  description: '',
  customer_id: '',
  property_id: '',
  stage: 'new',
  value: ''
})

export type OpportunityFieldErrors = Partial<Record<keyof OpportunityDraft, string>>

const VALUE_PATTERN = /^\d+(\.\d{1,2})?$/

export const validateOpportunityDraft = (draft: OpportunityDraft): OpportunityFieldErrors => {
  const errors: OpportunityFieldErrors = {}

  if (!draft.title.trim()) errors.title = 'Title is required.'
  if (!draft.customer_id) errors.customer_id = 'Customer is required.'

  const value = draft.value.trim()

  if (value && !VALUE_PATTERN.test(value)) {
    errors.value = 'Value must be a valid number.'
  }

  return errors
}

export const formatPipelineValue = (value: string | number | null | undefined): string => {
  if (value == null || value === '') return ''

  const numeric = typeof value === 'number' ? value : Number(value)

  if (!Number.isFinite(numeric)) return String(value)

  return `MYR ${numeric.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`
}

export const isPipelineStage = (value: string): value is PipelineStage =>
  value === 'new' ||
  value === 'qualified' ||
  value === 'quoted' ||
  value === 'negotiating' ||
  value === 'won' ||
  value === 'lost'

export const staffName = (opportunity: Pick<Opportunity, 'assigned_user' | 'assigned_to'>): string | null => {
  const name =
    opportunity.assigned_user?.name?.trim() ||
    opportunity.assigned_user?.display_name?.trim() ||
    opportunity.assigned_to?.name?.trim() ||
    opportunity.assigned_to?.display_name?.trim() ||
    ''

  return name || null
}

export const workflowActionLabel = (action: WorkflowAction): string => {
  if (action === 'qualify') return 'Qualify'
  if (action === 'quote') return 'Quote'
  if (action === 'approve') return 'Approve'
  if (action === 'move_to_finance') return 'Move to Finance'
  if (action === 'reopen') return 'Reopen'

  return action
}
