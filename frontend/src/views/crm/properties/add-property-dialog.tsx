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
import { isApiError } from '@/lib/api'
import { propertiesApi } from '@/lib/properties/api'
import type { Property, PropertyDraft } from '@/lib/properties/types'
import { draftFromProperty, emptyPropertyDraft, propertyPayloadFromDraft, validatePropertyDraft } from '@/lib/properties/validation'

import PropertyFormFields from './property-form-fields'

type AddPropertyDialogProps = {
  open: boolean
  property?: Property | null
  onOpenChange: (open: boolean) => void
  onSaved: (property: Property) => void
}

type PropertyFormFieldsProps = {
  property?: Property | null
  onClose: () => void
  onSaved: (property: Property) => void
}

const PropertyEditor = ({ property, onClose, onSaved }: PropertyFormFieldsProps) => {
  const [draft, setDraft] = useState<PropertyDraft>(property ? draftFromProperty(property) : emptyPropertyDraft())
  const [errors, setErrors] = useState<ReturnType<typeof validatePropertyDraft>>({})
  const [submitting, setSubmitting] = useState(false)
  const isEdit = property != null

  const submit = async () => {
    const nextErrors = validatePropertyDraft(draft)

    setErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) return

    setSubmitting(true)

    try {
      const payload = propertyPayloadFromDraft(draft)
      const saved = isEdit ? await propertiesApi.update(property.id, payload) : await propertiesApi.create(payload)

      toast.success(isEdit ? 'Property updated.' : 'Property created.')
      onSaved(saved)
      onClose()
    } catch (error) {
      toast.error(isApiError(error) ? error.message : 'Unable to save the property.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <PropertyFormFields
        draft={draft}
        errors={errors}
        idPrefix='property'
        onChange={patch => setDraft(current => ({ ...current, ...patch }))}
      />
      <DialogFooter>
        <Button variant='outline' onClick={onClose}>
          Cancel
        </Button>
        <Button onClick={() => void submit()} disabled={submitting}>
          {submitting ? 'Saving…' : isEdit ? 'Save Property' : 'Add Property'}
        </Button>
      </DialogFooter>
    </>
  )
}

const AddPropertyDialog = ({ open, property, onOpenChange, onSaved }: AddPropertyDialogProps) => {
  const isEdit = property != null

  return (
    <Dialog
      open={open}
      onOpenChange={next => {
        if (!next) onOpenChange(false)
        else onOpenChange(true)
      }}
    >
      <DialogContent className='max-h-[min(100dvh,42rem)] overflow-y-auto sm:max-w-2xl'>
        <DialogHeader>
          <DialogTitle>{isEdit ? 'Edit Property' : 'Add Property'}</DialogTitle>
        </DialogHeader>
        {open && (
          <PropertyEditor
            key={property?.id ?? 'new'}
            property={property}
            onClose={() => onOpenChange(false)}
            onSaved={onSaved}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

export default AddPropertyDialog
