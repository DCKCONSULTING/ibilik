'use client'

import { useEffect, useRef, useState } from 'react'

import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { useAuth } from '@/components/auth/auth-provider'
import { isApiError } from '@/lib/api'
import { paymentsApi } from '@/lib/payments/api'
import type { Payment } from '@/lib/payments/types'

const METHODS = [
  { id: 'cash', label: 'Cash' },
  { id: 'credit_card', label: 'Card' },
  { id: 'debit_card', label: 'Debit card' },
  { id: 'bank_transfer', label: 'Bank transfer' },
  { id: 'online', label: 'Online payment' },
  { id: 'other', label: 'Other' }
]

const CHARGE_CATEGORIES = [
  { id: 'extra_bed', label: 'Extra bed' },
  { id: 'food_beverage', label: 'Food and beverage' },
  { id: 'laundry', label: 'Laundry' },
  { id: 'room_service', label: 'Room service' },
  { id: 'late_checkout', label: 'Late checkout' },
  { id: 'additional_guest', label: 'Additional guest' },
  { id: 'damage', label: 'Damage charge' },
  { id: 'other', label: 'Other' }
]

const PENALTY_CATEGORIES = [
  { id: 'late_checkout', label: 'Late checkout' },
  { id: 'cancellation', label: 'Cancellation fee' },
  { id: 'no_show', label: 'No-show fee' },
  { id: 'damage', label: 'Damage penalty' },
  { id: 'lost_key', label: 'Lost key' },
  { id: 'extra_cleaning', label: 'Extra cleaning' },
  { id: 'other', label: 'Other' }
]

type DialogKind = 'payment' | 'charge' | 'penalty' | 'refund' | 'void' | null

type PaymentManagementDialogsProps = {
  payment: Payment
  action: DialogKind
  canReceive: boolean
  canCompleteRefund: boolean
  voidSourceId?: number
  onOpenChange: (open: boolean) => void
  onUpdated: (payment: Payment) => void
}

const PaymentManagementDialogs = ({
  payment,
  action,
  canReceive,
  canCompleteRefund,
  voidSourceId,
  onOpenChange,
  onUpdated
}: PaymentManagementDialogsProps) => {
  const { user } = useAuth()
  const [amount, setAmount] = useState('')
  const [method, setMethod] = useState('cash')
  const [reference, setReference] = useState('')
  const [notes, setNotes] = useState('')
  const [reason, setReason] = useState('')
  const [category, setCategory] = useState('other')
  const [description, setDescription] = useState('')
  const [quantity, setQuantity] = useState('1')
  const [unitPrice, setUnitPrice] = useState('')
  const [tax, setTax] = useState('0')
  const [paymentId, setPaymentId] = useState(String(payment.id))
  const [paidAt, setPaidAt] = useState(() => new Date().toISOString().slice(0, 16))
  const [submitting, setSubmitting] = useState(false)
  const idempotencyKey = useRef('')

  useEffect(() => {
    idempotencyKey.current = typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `pay-${action}-${payment.id}`
    setPaymentId(String(payment.id))
  }, [action, payment.id])

  const refundablePayments = (payment.ledger || [])
    .filter(item => item.source === 'payment' && item.status === 'approved')
    .map(item => ({
      id: String(item.source_id),
      label: [item.reference, item.method_label, item.amount ? `${payment.currency} ${item.amount}` : '']
        .filter(Boolean)
        .join(' · ')
    }))

  const paymentOptions = refundablePayments.length
    ? refundablePayments
    : [
        {
          id: String(payment.id),
          label: [payment.payment_number, payment.payment_method_label, payment.amount_label || payment.amount]
            .filter(Boolean)
            .join(' · ')
        }
      ]

  const close = () => {
    setAmount('')
    setMethod('cash')
    setReference('')
    setNotes('')
    setReason('')
    setCategory('other')
    setDescription('')
    setQuantity('1')
    setUnitPrice('')
    setTax('0')
    setPaidAt(new Date().toISOString().slice(0, 16))
    setSubmitting(false)
    onOpenChange(false)
  }

  const run = async (task: () => Promise<Payment>, success: string) => {
    if (submitting) return
    setSubmitting(true)

    try {
      const next = await task()

      toast.success(success)
      onUpdated(next)
      close()
    } catch (error) {
      toast.error(isApiError(error) ? error.message : 'Unable to save this transaction.')
      setSubmitting(false)
    }
  }

  if (!action) return null

  const titles = {
    payment: 'Add payment',
    charge: 'Add charge',
    penalty: 'Add penalty',
    refund: 'Refund payment',
    void: 'Void transaction'
  }

  const submit = () => {
    if (action === 'payment') {
      return run(async () => {
        await paymentsApi.create({
          case_id: payment.case.id,
          payment_type: 'payment',
          amount,
          currency: payment.currency,
          payment_method: method,
          paid_at: paidAt ? new Date(paidAt).toISOString() : new Date().toISOString(),
          notes: [reference, notes].filter(Boolean).join(' · '),
          received: canReceive || method === 'cash',
          idempotency_key: idempotencyKey.current
        })

        return paymentsApi.get(payment.id)
      }, 'Payment recorded.')
    }

    if (action === 'charge') {
      return run(
        () =>
          paymentsApi.addCharge(payment.id, {
            category,
            description,
            quantity,
            unit_price: unitPrice || amount,
            tax,
            notes,
            idempotency_key: idempotencyKey.current
          }),
        'Charge added.'
      )
    }

    if (action === 'penalty') {
      return run(
        () =>
          paymentsApi.addPenalty(payment.id, {
            category,
            description,
            amount: unitPrice || amount,
            unit_price: unitPrice || amount,
            quantity: '1',
            reason,
            notes,
            idempotency_key: idempotencyKey.current
          }),
        'Penalty added.'
      )
    }

    if (action === 'refund') {
      return run(async () => {
        await paymentsApi.requestRefund(Number(paymentId), {
          amount,
          reason,
          complete: canCompleteRefund
        })

        return paymentsApi.get(payment.id)
      }, canCompleteRefund ? 'Refund recorded.' : 'Refund requested.')
    }

    if (action === 'void' && voidSourceId) {
      return run(() => paymentsApi.voidCharge(voidSourceId, reason), 'Transaction voided.')
    }

    return undefined
  }

  return (
    <Dialog open onOpenChange={open => !open && close()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{titles[action]}</DialogTitle>
        </DialogHeader>
        <FieldGroup>
          {action === 'refund' && (
            <Field>
              <FieldLabel>Original payment</FieldLabel>
              <Select value={paymentId} onValueChange={value => value && setPaymentId(value)}>
                <SelectTrigger className='w-full'>
                  <SelectValue placeholder='Select a payment'>
                    {(value: string) =>
                      paymentOptions.find(item => item.id === value)?.label || payment.payment_number
                    }
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {paymentOptions.map(item => (
                    <SelectItem key={item.id} value={item.id}>
                      {item.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
          )}
          {action !== 'void' && (
            <Field>
              <FieldLabel>{action === 'charge' ? 'Unit price' : 'Amount'}</FieldLabel>
              <Input value={action === 'charge' ? unitPrice : amount} onChange={event => (action === 'charge' ? setUnitPrice(event.target.value) : setAmount(event.target.value))} />
            </Field>
          )}
          {action === 'payment' && (
            <Field>
              <FieldLabel>Payment date</FieldLabel>
              <Input type='datetime-local' value={paidAt} onChange={event => setPaidAt(event.target.value)} />
            </Field>
          )}
          {action === 'payment' && (
            <Field>
              <FieldLabel>Payment method</FieldLabel>
              <Select value={method} onValueChange={value => value && setMethod(value)}>
                <SelectTrigger className='w-full'>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {METHODS.map(item => (
                    <SelectItem key={item.id} value={item.id}>
                      {item.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
          )}
          {(action === 'charge' || action === 'penalty') && (
            <>
              <Field>
                <FieldLabel>{action === 'penalty' ? 'Penalty type' : 'Charge category'}</FieldLabel>
                <Select value={category} onValueChange={value => value && setCategory(value)}>
                  <SelectTrigger className='w-full'>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(action === 'penalty' ? PENALTY_CATEGORIES : CHARGE_CATEGORIES).map(item => (
                      <SelectItem key={item.id} value={item.id}>
                        {item.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
              <Field>
                <FieldLabel>Description</FieldLabel>
                <Input value={description} onChange={event => setDescription(event.target.value)} />
              </Field>
            </>
          )}
          {action === 'charge' && (
            <>
              <Field>
                <FieldLabel>Quantity</FieldLabel>
                <Input value={quantity} onChange={event => setQuantity(event.target.value)} />
              </Field>
              <Field>
                <FieldLabel>Tax</FieldLabel>
                <Input value={tax} onChange={event => setTax(event.target.value)} />
              </Field>
            </>
          )}
          {action === 'payment' && (
            <>
              <Field>
                <FieldLabel>Reference number</FieldLabel>
                <Input value={reference} onChange={event => setReference(event.target.value)} />
              </Field>
              <Field>
                <FieldLabel>Received by</FieldLabel>
                <Input value={user?.display_name || user?.username || ''} readOnly />
              </Field>
              <Field>
                <FieldLabel>Currency</FieldLabel>
                <Input value={payment.currency} readOnly />
              </Field>
            </>
          )}
          {(action === 'refund' || action === 'penalty' || action === 'void') && (
            <Field>
              <FieldLabel>Reason</FieldLabel>
              <Textarea value={reason} onChange={event => setReason(event.target.value)} rows={3} />
            </Field>
          )}
          {action !== 'void' && (
            <Field>
              <FieldLabel>Notes</FieldLabel>
              <Textarea value={notes} onChange={event => setNotes(event.target.value)} rows={2} />
            </Field>
          )}
        </FieldGroup>
        <DialogFooter>
          <Button type='button' variant='ghost' onClick={close}>
            Cancel
          </Button>
          <Button
            type='button'
            disabled={
              submitting ||
              ((action === 'refund' || action === 'penalty' || action === 'void') && !reason.trim()) ||
              (action !== 'void' && action !== 'charge' && !amount.trim()) ||
              (action === 'charge' && !unitPrice.trim() && !amount.trim())
            }
            onClick={() => void submit()}
          >
            Confirm
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default PaymentManagementDialogs
export type { DialogKind }
