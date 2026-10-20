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
import type { Customer, CustomerDraft } from '@/lib/customers/types'
import { emptyCustomerDraft, validateCustomerDraft } from '@/lib/customers/validation'
import { propertiesApi } from '@/lib/properties/api'
import type { Property } from '@/lib/properties/types'

type AddCustomerDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: (customer: Customer) => void
}

const AddCustomerDialog = ({ open, onOpenChange, onCreated }: AddCustomerDialogProps) => {
  const [draft, setDraft] = useState<CustomerDraft>(emptyCustomerDraft())
  const [errors, setErrors] = useState<ReturnType<typeof validateCustomerDraft>>({})
  const [submitting, setSubmitting] = useState(false)
  const [properties, setProperties] = useState<Property[]>([])

  useEffect(() => {
    if (!open) return

    propertiesApi
      .list()
      .then(payload => setProperties(payload.results))
      .catch(() => setProperties([]))
  }, [open])

  const close = () => {
    onOpenChange(false)
    setDraft(emptyCustomerDraft())
    setErrors({})
  }

  const submit = async () => {
    const nextErrors = validateCustomerDraft(draft)

    setErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) return

    setSubmitting(true)

    try {
      const created = await customersApi.create({
        name: draft.name.trim(),
        email: draft.email.trim(),
        phone: draft.phone.trim(),
        status: draft.status,
        notes: draft.notes.trim(),
        property_id: draft.property_id ? Number(draft.property_id) : undefined
      })

      toast.success('Customer created.')
      onCreated(created)
      close()
    } catch (error) {
      toast.error(isApiError(error) ? error.message : 'Unable to create the customer.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={next => {
        if (!next) close()
        else onOpenChange(true)
      }}
    >
      <DialogContent className='max-h-[min(100dvh,40rem)] overflow-y-auto sm:max-w-md'>
        <DialogHeader>
          <DialogTitle>Create New Customer</DialogTitle>
        </DialogHeader>
        <FieldGroup className='gap-4'>
          <Field data-invalid={Boolean(errors.name)}>
            <FieldLabel htmlFor='customer-name'>Name</FieldLabel>
            <Input
              id='customer-name'
              value={draft.name}
              aria-invalid={Boolean(errors.name)}
              onChange={event => setDraft(current => ({ ...current, name: event.target.value }))}
            />
            {errors.name && <FieldError>{errors.name}</FieldError>}
          </Field>
          <Field data-invalid={Boolean(errors.phone)}>
            <FieldLabel htmlFor='customer-phone'>Phone</FieldLabel>
            <Input
              id='customer-phone'
              value={draft.phone}
              aria-invalid={Boolean(errors.phone)}
              onChange={event => setDraft(current => ({ ...current, phone: event.target.value }))}
            />
            {errors.phone && <FieldError>{errors.phone}</FieldError>}
          </Field>
          <Field data-invalid={Boolean(errors.email)}>
            <FieldLabel htmlFor='customer-email'>Email</FieldLabel>
            <Input
              id='customer-email'
              type='email'
              value={draft.email}
              aria-invalid={Boolean(errors.email)}
              onChange={event => setDraft(current => ({ ...current, email: event.target.value }))}
            />
            {errors.email && <FieldError>{errors.email}</FieldError>}
          </Field>
          <Field>
            <FieldLabel>Status</FieldLabel>
            <Select value={draft.status} onValueChange={value => value && setDraft(current => ({ ...current, status: value as CustomerDraft['status'] }))}>
              <SelectTrigger className='w-full'>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value='lead'>Lead</SelectItem>
                <SelectItem value='active'>Active</SelectItem>
                <SelectItem value='archived'>Archived</SelectItem>
              </SelectContent>
            </Select>
          </Field>
          <Field>
            <FieldLabel>Property interest</FieldLabel>
            <Select
              value={draft.property_id || null}
              onValueChange={value => setDraft(current => ({ ...current, property_id: value ?? '' }))}
            >
              <SelectTrigger className='w-full'>
                <SelectValue placeholder='None' />
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
            <FieldLabel htmlFor='customer-notes'>Notes</FieldLabel>
            <Textarea
              id='customer-notes'
              value={draft.notes}
              onChange={event => setDraft(current => ({ ...current, notes: event.target.value }))}
            />
          </Field>
        </FieldGroup>
        <DialogFooter>
          <Button variant='outline' onClick={close}>
            Cancel
          </Button>
          <Button onClick={() => void submit()} disabled={submitting}>
            {submitting ? 'Saving…' : 'Create Customer'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default AddCustomerDialog
