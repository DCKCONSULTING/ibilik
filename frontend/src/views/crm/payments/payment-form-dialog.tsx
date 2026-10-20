'use client'

import { useEffect, useState } from 'react'

import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { isApiError } from '@/lib/api'
import { casesApi } from '@/lib/pipeline/api'
import type { Opportunity } from '@/lib/pipeline/types'
import { paymentsApi } from '@/lib/payments/api'
import type { Payment } from '@/lib/payments/types'

type Option = { id: string; label: string }

type PaymentFormDialogProps = {
  open: boolean
  caseRecord?: Opportunity | null
  allowCaseSelect?: boolean
  types?: Option[]
  methods?: Option[]
  onOpenChange: (open: boolean) => void
  onSaved: (payment?: Payment) => void
}

const toIso = (date: string, time: string) => {
  if (!date) return null

  const next = new Date(`${date}T${time || '09:00'}`)

  return Number.isNaN(next.getTime()) ? null : next.toISOString()
}

const PaymentFormDialog = ({
  open,
  caseRecord = null,
  allowCaseSelect = false,
  types = [
    { id: 'deposit', label: 'Deposit' },
    { id: 'payment', label: 'Payment' }
  ],
  methods = [
    { id: 'bank_transfer', label: 'Bank Transfer' },
    { id: 'cash', label: 'Cash' },
    { id: 'credit_card', label: 'Credit Card' },
    { id: 'debit_card', label: 'Debit Card' },
    { id: 'online', label: 'Online Payment' },
    { id: 'other', label: 'Other' }
  ],
  onOpenChange,
  onSaved
}: PaymentFormDialogProps) => {
  const [paymentType, setPaymentType] = useState('deposit')
  const [amount, setAmount] = useState('')
  const [currency, setCurrency] = useState('MYR')
  const [method, setMethod] = useState('bank_transfer')
  const [expectedDate, setExpectedDate] = useState('')
  const [expectedTime, setExpectedTime] = useState('09:00')
  const [paidDate, setPaidDate] = useState('')
  const [paidTime, setPaidTime] = useState('09:00')
  const [notes, setNotes] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [caseQuery, setCaseQuery] = useState('')
  const [caseOptions, setCaseOptions] = useState<Opportunity[]>([])
  const [selectedCaseId, setSelectedCaseId] = useState(caseRecord ? String(caseRecord.id) : '')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!open || !allowCaseSelect) return

    const handle = window.setTimeout(() => {
      void casesApi
        .list({ search: caseQuery.trim() || undefined, page_size: 25 })
        .then(payload => setCaseOptions(payload.results))
        .catch(() => setCaseOptions([]))
    }, 250)

    return () => window.clearTimeout(handle)
  }, [allowCaseSelect, caseQuery, open])

  const selectedCase =
    caseRecord || caseOptions.find(item => String(item.id) === selectedCaseId) || null

  const submit = async () => {
    const caseId = caseRecord?.id || Number(selectedCaseId)

    if (!caseId) {
      toast.error('Select a case.')

      return
    }

    if (!amount.trim() || Number(amount) <= 0) {
      toast.error('Amount must be greater than zero.')

      return
    }

    setSubmitting(true)

    try {
      const created = await paymentsApi.create({
        case_id: caseId,
        payment_type: paymentType,
        amount: amount.trim(),
        currency: currency.trim() || 'MYR',
        payment_method: method,
        expected_date: toIso(expectedDate, expectedTime),
        paid_at: toIso(paidDate, paidTime),
        notes: notes.trim()
      })

      if (file) {
        await paymentsApi.uploadAttachment(created.id, file, 'Payment proof')
      }

      toast.success('Payment created.')
      onSaved(created)
      onOpenChange(false)
    } catch (error) {
      toast.error(isApiError(error) ? error.message : 'Unable to create this payment.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={next => !next && onOpenChange(false)}>
      <DialogContent className='sm:max-w-lg'>
        <DialogHeader>
          <DialogTitle>New payment</DialogTitle>
        </DialogHeader>
        <FieldGroup>
          {allowCaseSelect && (
            <Field>
              <FieldLabel>Case</FieldLabel>
              <Input
                value={caseQuery}
                onChange={event => setCaseQuery(event.target.value)}
                placeholder='Search case, customer...'
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
          {selectedCase && (
            <p className='text-muted-foreground text-sm'>
              {selectedCase.customer.name}
              {selectedCase.property ? ` · ${selectedCase.property.name}` : ''}
            </p>
          )}
          <Field>
            <FieldLabel>Payment Type</FieldLabel>
            <Select value={paymentType} onValueChange={value => value && setPaymentType(value)}>
              <SelectTrigger>
                <SelectValue />
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
          <div className='grid gap-3 sm:grid-cols-2'>
            <Field>
              <FieldLabel>Amount</FieldLabel>
              <Input value={amount} onChange={event => setAmount(event.target.value)} placeholder='5000' />
            </Field>
            <Field>
              <FieldLabel>Currency</FieldLabel>
              <Input value={currency} onChange={event => setCurrency(event.target.value)} />
            </Field>
          </div>
          <Field>
            <FieldLabel>Payment Method</FieldLabel>
            <Select value={method} onValueChange={value => value && setMethod(value)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {methods.map(item => (
                  <SelectItem key={item.id} value={item.id}>
                    {item.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <div className='grid gap-3 sm:grid-cols-2'>
            <Field>
              <FieldLabel>Expected Date</FieldLabel>
              <Input type='date' value={expectedDate} onChange={event => setExpectedDate(event.target.value)} />
            </Field>
            <Field>
              <FieldLabel>Expected Time</FieldLabel>
              <Input type='time' value={expectedTime} onChange={event => setExpectedTime(event.target.value)} />
            </Field>
          </div>
          <div className='grid gap-3 sm:grid-cols-2'>
            <Field>
              <FieldLabel>Payment Date</FieldLabel>
              <Input type='date' value={paidDate} onChange={event => setPaidDate(event.target.value)} />
            </Field>
            <Field>
              <FieldLabel>Payment Time</FieldLabel>
              <Input type='time' value={paidTime} onChange={event => setPaidTime(event.target.value)} />
            </Field>
          </div>
          <Field>
            <FieldLabel>Notes</FieldLabel>
            <Textarea value={notes} onChange={event => setNotes(event.target.value)} rows={3} />
          </Field>
          <Field>
            <FieldLabel>Attachment</FieldLabel>
            <Input type='file' onChange={event => setFile(event.target.files?.[0] ?? null)} />
          </Field>
        </FieldGroup>
        <DialogFooter>
          <Button type='button' variant='ghost' onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type='button' disabled={submitting} onClick={() => void submit()}>
            Create payment
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default PaymentFormDialog
