'use client'

import { useEffect, useState } from 'react'

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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { isApiError } from '@/lib/api'
import { customersApi } from '@/lib/customers/api'
import type { Customer } from '@/lib/customers/types'
import { pipelineApi } from '@/lib/pipeline/api'
import type { Opportunity, OpportunityDraft } from '@/lib/pipeline/types'
import { PIPELINE_STAGES } from '@/lib/pipeline/types'
import { emptyOpportunityDraft, isPipelineStage, validateOpportunityDraft } from '@/lib/pipeline/validation'
import { propertiesApi } from '@/lib/properties/api'
import type { Property } from '@/lib/properties/types'

type AddOpportunityDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: (opportunity: Opportunity) => void
}

const AddOpportunityDialog = ({ open, onOpenChange, onCreated }: AddOpportunityDialogProps) => {
  const [draft, setDraft] = useState<OpportunityDraft>(emptyOpportunityDraft())
  const [errors, setErrors] = useState<ReturnType<typeof validateOpportunityDraft>>({})
  const [submitting, setSubmitting] = useState(false)
  const [customers, setCustomers] = useState<Customer[]>([])
  const [properties, setProperties] = useState<Property[]>([])

  useEffect(() => {
    if (!open) return

    customersApi
      .list({ page_size: 100 })
      .then(payload => setCustomers(payload.results))
      .catch(() => setCustomers([]))

    propertiesApi
      .list()
      .then(payload => setProperties(payload.results))
      .catch(() => setProperties([]))
  }, [open])

  const close = () => {
    onOpenChange(false)
    setDraft(emptyOpportunityDraft())
    setErrors({})
  }

  const submit = async () => {
    const nextErrors = validateOpportunityDraft(draft)

    setErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) return

    setSubmitting(true)

    try {
      const created = await pipelineApi.create({
        title: draft.title.trim(),
        description: draft.description.trim() || undefined,
        customer_id: Number(draft.customer_id),
        property_id: draft.property_id ? Number(draft.property_id) : undefined,
        stage: draft.stage,
        value: draft.value.trim() || undefined
      })

      toast.success('Case created.')
      onCreated(created)
      close()
    } catch (error) {
      toast.error(isApiError(error) ? error.message : 'Unable to create the pipeline record.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={next => (next ? onOpenChange(true) : close())}>
      <DialogContent className='sm:max-w-lg'>
        <DialogHeader>
          <DialogTitle>New case</DialogTitle>
        </DialogHeader>
        <FieldGroup>
          <Field data-invalid={Boolean(errors.title)}>
            <FieldLabel htmlFor='opportunity-title'>Title</FieldLabel>
            <Input
              id='opportunity-title'
              value={draft.title}
              aria-invalid={Boolean(errors.title)}
              onChange={event => setDraft(current => ({ ...current, title: event.target.value }))}
            />
            {errors.title && <FieldError>{errors.title}</FieldError>}
          </Field>
          <Field data-invalid={Boolean(errors.customer_id)}>
            <FieldLabel>Customer</FieldLabel>
            <Select
              value={draft.customer_id || null}
              onValueChange={value => {
                if (!value) return

                const customer = customers.find(item => String(item.id) === value)

                const matchingProperty = customer?.properties?.find(item =>
                  properties.some(property => property.id === item.id)
                )

                setDraft(current => ({
                  ...current,
                  customer_id: value,
                  property_id: current.property_id || (matchingProperty ? String(matchingProperty.id) : current.property_id)
                }))
              }}
            >
              <SelectTrigger aria-invalid={Boolean(errors.customer_id)}>
                <SelectValue placeholder='Select a customer' />
              </SelectTrigger>
              <SelectContent>
                {customers.map(customer => (
                  <SelectItem key={customer.id} value={String(customer.id)}>
                    {customer.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {errors.customer_id && <FieldError>{errors.customer_id}</FieldError>}
          </Field>
          <Field>
            <FieldLabel>Property</FieldLabel>
            <Select
              value={draft.property_id || null}
              onValueChange={value => value && setDraft(current => ({ ...current, property_id: value }))}
            >
              <SelectTrigger>
                <SelectValue placeholder='Select a property' />
              </SelectTrigger>
              <SelectContent>
                {properties.map(property => (
                  <SelectItem key={property.id} value={String(property.id)}>
                    {property.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <Field>
            <FieldLabel>Stage</FieldLabel>
            <Select
              value={draft.stage}
              onValueChange={value => value && isPipelineStage(value) && setDraft(current => ({ ...current, stage: value }))}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PIPELINE_STAGES.map(stage => (
                  <SelectItem key={stage.id} value={stage.id}>
                    {stage.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <Field data-invalid={Boolean(errors.value)}>
            <FieldLabel htmlFor='opportunity-value'>Expected value</FieldLabel>
            <Input
              id='opportunity-value'
              value={draft.value}
              aria-invalid={Boolean(errors.value)}
              onChange={event => setDraft(current => ({ ...current, value: event.target.value }))}
            />
            {errors.value && <FieldError>{errors.value}</FieldError>}
          </Field>
          <Field>
            <FieldLabel htmlFor='opportunity-description'>Description</FieldLabel>
            <Textarea
              id='opportunity-description'
              value={draft.description}
              onChange={event => setDraft(current => ({ ...current, description: event.target.value }))}
            />
          </Field>
        </FieldGroup>
        <DialogFooter>
          <Button type='button' variant='outline' onClick={close}>
            Cancel
          </Button>
          <Button type='button' onClick={() => void submit()} disabled={submitting}>
            {submitting ? 'Saving…' : 'Create'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default AddOpportunityDialog
