'use client'

import { useState } from 'react'

import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog'
import { Field, FieldError, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { isApiError } from '@/lib/api'
import { pipelineApi } from '@/lib/pipeline/api'
import type { Opportunity } from '@/lib/pipeline/types'

type QuoteOpportunityDialogProps = {
  opportunity: Opportunity | null
  onOpenChange: (open: boolean) => void
  onQuoted: (opportunity: Opportunity) => void
}

type QuoteFormProps = {
  opportunity: Opportunity
  onCancel: () => void
  onQuoted: (opportunity: Opportunity) => void
}

const QuoteForm = ({ opportunity, onCancel, onQuoted }: QuoteFormProps) => {
  const [value, setValue] = useState(opportunity.value ?? '')
  const [notes, setNotes] = useState(opportunity.quote_notes ?? '')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const submit = async () => {
    const trimmed = value.trim()

    if (trimmed && !/^\d+(\.\d{1,2})?$/.test(trimmed)) {
      setError('Value must be a valid number.')

      return
    }

    setSubmitting(true)

    try {
      const updated = await pipelineApi.performAction(opportunity.id, {
        action: 'quote',
        value: trimmed || undefined,
        notes: notes.trim()
      })

      toast.success('Quote saved and the opportunity moved to Quoted.')
      onQuoted(updated)
      onCancel()
    } catch (err) {
      toast.error(isApiError(err) ? err.message : 'Unable to save the quote.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <FieldGroup>
        <Field data-invalid={Boolean(error)}>
          <FieldLabel htmlFor='quote-value'>Quoted value</FieldLabel>
          <Input
            id='quote-value'
            value={value}
            aria-invalid={Boolean(error)}
            onChange={event => {
              setValue(event.target.value)
              setError(null)
            }}
          />
          {error && <FieldError>{error}</FieldError>}
        </Field>
        <Field>
          <FieldLabel htmlFor='quote-notes'>Notes</FieldLabel>
          <Textarea
            id='quote-notes'
            value={notes}
            onChange={event => setNotes(event.target.value)}
            placeholder='Rate, room type, or conditions to send to the customer.'
          />
        </Field>
      </FieldGroup>
      <DialogFooter>
        <Button type='button' variant='outline' onClick={onCancel}>
          Cancel
        </Button>
        <Button type='button' onClick={() => void submit()} disabled={submitting}>
          {submitting ? 'Saving…' : 'Save quote'}
        </Button>
      </DialogFooter>
    </>
  )
}

const QuoteOpportunityDialog = ({ opportunity, onOpenChange, onQuoted }: QuoteOpportunityDialogProps) => {
  const close = () => onOpenChange(false)

  return (
    <Dialog open={opportunity !== null} onOpenChange={next => (next ? onOpenChange(true) : close())}>
      <DialogContent className='sm:max-w-md'>
        <DialogHeader>
          <DialogTitle>Quote {opportunity?.title}</DialogTitle>
        </DialogHeader>
        {opportunity && (
          <QuoteForm key={opportunity.id} opportunity={opportunity} onCancel={close} onQuoted={onQuoted} />
        )}
      </DialogContent>
    </Dialog>
  )
}

export default QuoteOpportunityDialog
