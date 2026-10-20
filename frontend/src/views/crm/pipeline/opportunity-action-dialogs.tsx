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
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Textarea } from '@/components/ui/textarea'
import { isApiError } from '@/lib/api'
import { authApi } from '@/lib/auth/api'
import type { AuthUser } from '@/lib/auth/types'
import { formatLastContact } from '@/lib/customers/validation'
import { pipelineApi } from '@/lib/pipeline/api'
import type { Opportunity } from '@/lib/pipeline/types'
import { staffName } from '@/lib/pipeline/validation'
import { propertiesApi } from '@/lib/properties/api'

type TransferDialogProps = {
  opportunity: Opportunity | null
  canViewUsers: boolean
  onOpenChange: (open: boolean) => void
  onTransferred: (opportunity: Opportunity) => void
}

type StaffOption = {
  id: number
  label: string
}

export const TransferOpportunityDialog = ({
  opportunity,
  canViewUsers,
  onOpenChange,
  onTransferred
}: TransferDialogProps) => {
  const [staff, setStaff] = useState<StaffOption[]>([])
  const [selected, setSelected] = useState('unassigned')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!opportunity) return

    let mounted = true

    const load = async () => {
      const options: StaffOption[] = []

      if (canViewUsers) {
        const payload = await authApi.listUsers()

        payload.results.forEach(user => {
          options.push({ id: user.id, label: user.display_name || user.username })
        })
      } else if (opportunity.property) {
        const payload = await propertiesApi.listStaff(opportunity.property.id)

        payload.results.forEach(user => {
          options.push({ id: user.id, label: user.display_name || user.username })
        })
      }

      const current = opportunity.assigned_to || opportunity.assigned_user

      if (current && !options.some(item => item.id === current.id)) {
        options.unshift({ id: current.id, label: current.display_name || current.name || current.username })
      }

      if (!mounted) return

      setStaff(options)
      setSelected(current?.id ? String(current.id) : 'unassigned')
    }

    load().catch(() => {
      if (!mounted) return

      setStaff([])
    })

    return () => {
      mounted = false
    }
  }, [canViewUsers, opportunity])

  const submit = async () => {
    if (!opportunity) return

    setSubmitting(true)

    try {
      const updated = await pipelineApi.update(opportunity.id, {
        assigned_to_id: selected === 'unassigned' ? null : Number(selected)
      })

      toast.success(selected === 'unassigned' ? 'Opportunity is now unassigned.' : 'Opportunity transferred.')
      onTransferred(updated)
      onOpenChange(false)
    } catch (error) {
      toast.error(isApiError(error) ? error.message : 'Unable to transfer this opportunity.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={opportunity !== null} onOpenChange={open => !open && onOpenChange(false)}>
      <DialogContent className='sm:max-w-md'>
        <DialogHeader>
          <DialogTitle>Transfer opportunity</DialogTitle>
        </DialogHeader>
        <FieldGroup>
          <Field>
            <FieldLabel>Assign to</FieldLabel>
            <Select value={selected} onValueChange={value => value && setSelected(value)}>
              <SelectTrigger>
                <SelectValue placeholder='Unassigned' />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value='unassigned'>Unassigned</SelectItem>
                {staff.map(user => (
                  <SelectItem key={user.id} value={String(user.id)}>
                    {user.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
        </FieldGroup>
        <DialogFooter>
          <Button type='button' variant='outline' onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type='button' onClick={() => void submit()} disabled={submitting}>
            {submitting ? 'Saving…' : 'Transfer'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

type AddNoteDialogProps = {
  opportunity: Opportunity | null
  user: AuthUser | null
  onOpenChange: (open: boolean) => void
  onSaved: (opportunity: Opportunity) => void
}

export const AddOpportunityNoteDialog = ({ opportunity, user, onOpenChange, onSaved }: AddNoteDialogProps) => {
  const [note, setNote] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const submit = async () => {
    if (!opportunity) return

    const text = note.trim()

    if (!text) {
      toast.error('Enter a note before saving.')

      return
    }

    const author = user?.display_name || user?.username || 'Staff'
    const stamp = new Date().toLocaleString()
    const entry = `${author} — ${stamp}\n${text}`
    const next = opportunity.staff_notes?.trim() ? `${opportunity.staff_notes.trim()}\n\n${entry}` : entry

    setSubmitting(true)

    try {
      const updated = await pipelineApi.update(opportunity.id, { staff_notes: next })

      toast.success('Note added.')
      onSaved(updated)
      setNote('')
      onOpenChange(false)
    } catch (error) {
      toast.error(isApiError(error) ? error.message : 'Unable to add the note.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog
      open={opportunity !== null}
      onOpenChange={open => {
        if (!open) {
          setNote('')
          onOpenChange(false)
        }
      }}
    >
      <DialogContent className='sm:max-w-md'>
        <DialogHeader>
          <DialogTitle>Add note</DialogTitle>
        </DialogHeader>
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor='opportunity-note'>Note</FieldLabel>
            <Textarea
              id='opportunity-note'
              value={note}
              onChange={event => setNote(event.target.value)}
              placeholder='Add an internal note for this opportunity.'
            />
          </Field>
        </FieldGroup>
        <DialogFooter>
          <Button type='button' variant='outline' onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type='button' onClick={() => void submit()} disabled={submitting}>
            {submitting ? 'Saving…' : 'Save note'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

type HistorySheetProps = {
  opportunity: Opportunity | null
  onOpenChange: (open: boolean) => void
}

const senderLabel = (value: string) => {
  if (value === 'bot') return 'AI Bot'
  if (value === 'staff') return 'Staff'
  if (value === 'system') return 'System'

  return 'Customer'
}

export const OpportunityHistorySheet = ({ opportunity, onOpenChange }: HistorySheetProps) => {
  const events = opportunity
    ? [
        { label: 'Created', at: opportunity.created_at },
        { label: 'Quoted', at: opportunity.quoted_at ?? null },
        { label: 'Approved', at: opportunity.approved_at ?? null },
        { label: 'Moved to finance', at: opportunity.finance_moved_at ?? null },
        { label: 'Last activity', at: opportunity.updated_at }
      ].filter(item => item.at)
    : []

  return (
    <Sheet open={opportunity !== null} onOpenChange={open => !open && onOpenChange(false)}>
      <SheetContent className='overflow-y-auto sm:max-w-lg'>
        <SheetHeader>
          <SheetTitle>History</SheetTitle>
        </SheetHeader>
        {opportunity && (
          <div className='flex flex-col gap-6 px-4 pb-6'>
            <section>
              <p className='text-muted-foreground text-xs'>Current staff</p>
              <p className='text-sm font-medium'>{staffName(opportunity) ?? 'Unassigned'}</p>
            </section>
            <section className='space-y-3'>
              <h3 className='font-medium'>Timeline</h3>
              <ol className='space-y-3'>
                {events.map(item => (
                  <li key={`${item.label}-${item.at}`} className='rounded-md border px-3 py-2'>
                    <p className='text-sm font-medium'>{item.label}</p>
                    <p className='text-muted-foreground text-xs'>{formatLastContact(item.at)}</p>
                  </li>
                ))}
              </ol>
            </section>
            <section className='space-y-2'>
              <h3 className='font-medium'>Notes</h3>
              {opportunity.staff_notes?.trim() ? (
                <p className='text-sm whitespace-pre-wrap'>{opportunity.staff_notes}</p>
              ) : (
                <p className='text-muted-foreground text-sm'>No staff notes yet.</p>
              )}
            </section>
            <section className='space-y-3'>
              <h3 className='font-medium'>Conversation</h3>
              {(opportunity.conversation?.messages ?? []).length === 0 ? (
                <p className='text-muted-foreground text-sm'>No conversation history is linked.</p>
              ) : (
                <ol className='space-y-3'>
                  {opportunity.conversation?.messages?.map(message => (
                    <li key={message.id} className='rounded-md border px-3 py-2'>
                      <p className='text-xs font-medium'>{senderLabel(message.sender_type)}</p>
                      <p className='mt-1 text-sm whitespace-pre-wrap'>{message.content}</p>
                    </li>
                  ))}
                </ol>
              )}
            </section>
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}
