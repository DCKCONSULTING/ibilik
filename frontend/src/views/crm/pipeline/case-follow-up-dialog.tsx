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
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { isApiError } from '@/lib/api'
import { authApi } from '@/lib/auth/api'
import { casesApi, followUpsApi } from '@/lib/pipeline/api'
import type { CaseFollowUp, FollowUpTypeId, Opportunity } from '@/lib/pipeline/types'
import { FOLLOW_UP_TYPES } from '@/lib/pipeline/types'
import { propertiesApi } from '@/lib/properties/api'

type StaffOption = {
  id: number
  label: string
}

type FollowUpDialogProps = {
  caseRecord?: Opportunity | null
  followUp?: CaseFollowUp | null
  open?: boolean
  allowCaseSelect?: boolean
  types?: { id: string; label: string }[]
  staffOptions?: StaffOption[]
  canViewUsers: boolean
  onOpenChange: (open: boolean) => void
  onSaved: (record?: Opportunity) => void
}

const splitDue = (value: string | null | undefined) => {
  if (!value) return { date: '', time: '09:00' }

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) return { date: '', time: '09:00' }

  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')

  return { date: `${year}-${month}-${day}`, time: `${hours}:${minutes}` }
}

const toDueAt = (date: string, time: string) => {
  if (!date) return null

  const next = new Date(`${date}T${time || '09:00'}`)

  return Number.isNaN(next.getTime()) ? null : next.toISOString()
}

const CaseFollowUpDialog = ({
  caseRecord = null,
  followUp = null,
  open,
  allowCaseSelect = false,
  types = FOLLOW_UP_TYPES,
  staffOptions = [],
  canViewUsers,
  onOpenChange,
  onSaved
}: FollowUpDialogProps) => {
  const visible = open ?? caseRecord !== null
  const current = followUp?.assigned_to || caseRecord?.assigned_to || caseRecord?.assigned_user
  const due = splitDue(followUp?.due_at)
  const [type, setType] = useState<FollowUpTypeId | string>(followUp?.type || 'follow_up')
  const [title, setTitle] = useState(followUp?.title || '')
  const [description, setDescription] = useState(followUp?.description || '')
  const [assigned, setAssigned] = useState(current?.id ? String(current.id) : 'unassigned')
  const [dueDate, setDueDate] = useState(due.date)
  const [dueTime, setDueTime] = useState(due.time)
  const [staff, setStaff] = useState<StaffOption[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [caseQuery, setCaseQuery] = useState('')
  const [caseOptions, setCaseOptions] = useState<Opportunity[]>([])
  const [selectedCaseId, setSelectedCaseId] = useState(followUp?.case_id ? String(followUp.case_id) : '')

  useEffect(() => {
    if (!visible) return

    let mounted = true

    const load = async () => {
      const options: StaffOption[] = []

      if (staffOptions.length > 0) {
        staffOptions.forEach(user => {
          if (!options.some(item => item.id === user.id)) options.push(user)
        })
      } else if (canViewUsers) {
        const payload = await authApi.listUsers()

        payload.results.forEach(user => {
          options.push({ id: user.id, label: user.display_name || user.username })
        })
      } else if (caseRecord?.property) {
        const payload = await propertiesApi.listStaff(caseRecord.property.id)

        payload.results.forEach(user => {
          options.push({ id: user.id, label: user.display_name || user.username })
        })
      }

      const currentStaff = followUp?.assigned_to || caseRecord?.assigned_to || caseRecord?.assigned_user

      if (currentStaff && !options.some(item => item.id === currentStaff.id)) {
        options.unshift({
          id: currentStaff.id,
          label: currentStaff.display_name || currentStaff.name || currentStaff.username
        })
      }

      if (!mounted) return

      setStaff(options)
    }

    load().catch(() => {
      if (mounted) setStaff([])
    })

    return () => {
      mounted = false
    }
  }, [canViewUsers, caseRecord, followUp, staffOptions, visible])

  useEffect(() => {
    if (!visible || !allowCaseSelect) return

    let mounted = true

    const handle = window.setTimeout(() => {
      casesApi
        .list({ search: caseQuery.trim() || undefined, page_size: 20 })
        .then(payload => {
          if (mounted) setCaseOptions(payload.results)
        })
        .catch(() => {
          if (mounted) setCaseOptions([])
        })
    }, 250)

    return () => {
      mounted = false
      window.clearTimeout(handle)
    }
  }, [allowCaseSelect, caseQuery, visible])

  const submit = async () => {
    const caseId = caseRecord?.id ?? followUp?.case_id ?? Number(selectedCaseId)

    if (!caseId) {
      toast.error('Select a case.')

      return
    }

    setSubmitting(true)

    try {
      const payload = {
        type,
        title: title.trim() || types.find(item => item.id === type)?.label || 'Follow Up',
        description: description.trim(),
        assigned_to_id: assigned === 'unassigned' ? null : Number(assigned),
        due_at: toDueAt(dueDate, dueTime)
      }

      if (caseRecord) {
        if (followUp) {
          await casesApi.updateFollowUp(caseRecord.id, followUp.id, payload)
          toast.success('Follow-up updated.')
        } else {
          await casesApi.createFollowUp(caseRecord.id, payload)
          toast.success('Follow-up created.')
        }

        const refreshed = await casesApi.get(caseRecord.id)

        onSaved(refreshed)
      } else if (followUp) {
        await followUpsApi.update(followUp.id, payload)
        toast.success('Follow-up updated.')
        onSaved()
      } else {
        await followUpsApi.create({ ...payload, case_id: caseId })
        toast.success('Follow-up created.')
        onSaved()
      }

      onOpenChange(false)
    } catch (error) {
      toast.error(isApiError(error) ? error.message : 'Unable to save this follow-up.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={visible} onOpenChange={next => !next && onOpenChange(false)}>
      <DialogContent className='sm:max-w-md'>
        <DialogHeader>
          <DialogTitle>{followUp ? 'Edit follow-up' : 'Add follow-up'}</DialogTitle>
        </DialogHeader>
        <FieldGroup>
          {allowCaseSelect && (
            <Field>
              <FieldLabel>Case</FieldLabel>
              <Input
                value={caseQuery}
                onChange={event => setCaseQuery(event.target.value)}
                placeholder='Search case number or customer'
              />
              <Select value={selectedCaseId} onValueChange={value => value && setSelectedCaseId(value)}>
                <SelectTrigger>
                  <SelectValue placeholder='Select a case' />
                </SelectTrigger>
                <SelectContent>
                  {caseOptions.map(item => (
                    <SelectItem key={item.id} value={String(item.id)}>
                      {item.case_number} · {item.customer.name} · {item.title}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
          )}
          <Field>
            <FieldLabel>Type</FieldLabel>
            <Select value={type} onValueChange={value => value && setType(value)}>
              <SelectTrigger>
                <SelectValue placeholder='Select type' />
              </SelectTrigger>
              <SelectContent>
                {types.map(item => (
                  <SelectItem key={item.id} value={item.id}>
                    {item.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <Field>
            <FieldLabel>Title</FieldLabel>
            <Input value={title} onChange={event => setTitle(event.target.value)} placeholder='Send quote' />
          </Field>
          <Field>
            <FieldLabel>Description</FieldLabel>
            <Textarea value={description} onChange={event => setDescription(event.target.value)} rows={3} />
          </Field>
          <Field>
            <FieldLabel>Assigned staff</FieldLabel>
            <Select value={assigned} onValueChange={value => value && setAssigned(value)}>
              <SelectTrigger>
                <SelectValue placeholder='Unassigned' />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value='unassigned'>Unassigned</SelectItem>
                {staff.map(item => (
                  <SelectItem key={item.id} value={String(item.id)}>
                    {item.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <div className='grid gap-3 sm:grid-cols-2'>
            <Field>
              <FieldLabel>Due date</FieldLabel>
              <Input type='date' value={dueDate} onChange={event => setDueDate(event.target.value)} />
            </Field>
            <Field>
              <FieldLabel>Due time</FieldLabel>
              <Input type='time' value={dueTime} onChange={event => setDueTime(event.target.value)} />
            </Field>
          </div>
        </FieldGroup>
        <DialogFooter>
          <Button type='button' variant='outline' onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type='button' disabled={submitting} onClick={() => void submit()}>
            {followUp ? 'Save follow-up' : 'Add follow-up'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default CaseFollowUpDialog
