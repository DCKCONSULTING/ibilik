'use client'

import { useState } from 'react'

import Link from 'next/link'

import { useAuth } from '@/components/auth/auth-provider'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Textarea } from '@/components/ui/textarea'
import { formatDueAt, formatRelativeTime } from '@/lib/datetime'
import type { Payment, PaymentRefund } from '@/lib/payments/types'
import { workflowStatus } from '@/lib/payments/types'
import { cn } from '@/lib/utils'

import PaymentManagementDialogs, { type DialogKind } from './payment-management-dialogs'

type PaymentDetailSheetProps = {
  payment: Payment | null
  canChange: boolean
  canApprove: boolean
  canReject: boolean
  canRemind: boolean
  canRequestRefund: boolean
  canManageRefund: boolean
  onOpenChange: (open: boolean) => void
  onCustomer: (payment: Payment) => void
  onSubmit: (payment: Payment) => void
  onApprove: (payment: Payment) => void
  onReject: (payment: Payment, reason: string) => void
  onRemind: (payment: Payment, channel?: string) => void
  onUpload: (payment: Payment, file: File) => void
  onRequestRefund: (payment: Payment, amount: string, reason: string) => void
  onApproveRefund: (refund: PaymentRefund) => void
  onRejectRefund: (refund: PaymentRefund, reason: string) => void
  onCompleteRefund: (refund: PaymentRefund) => void
  onUpdated?: (payment: Payment) => void
}

const channelLabel = (channel: string) => {
  if (channel === 'whatsapp') return 'Reply via WhatsApp'
  if (channel === 'facebook') return 'Reply via Facebook Messenger'

  return channel
}

const PaymentDetailSheet = ({
  payment,
  canChange,
  canApprove,
  canReject,
  canRemind,
  canRequestRefund,
  canManageRefund,
  onOpenChange,
  onCustomer,
  onSubmit,
  onApprove,
  onReject,
  onRemind,
  onUpload,
  onRequestRefund,
  onApproveRefund,
  onRejectRefund,
  onCompleteRefund,
  onUpdated
}: PaymentDetailSheetProps) => {
  const { can } = useAuth()
  const [action, setAction] = useState<DialogKind>(null)
  const [voidSourceId, setVoidSourceId] = useState<number | undefined>()
  const [rejectOpen, setRejectOpen] = useState(false)
  const [rejectReason, setRejectReason] = useState('')
  const [refundOpen, setRefundOpen] = useState(false)
  const [refundAmount, setRefundAmount] = useState('')
  const [refundReason, setRefundReason] = useState('')
  const [refundReject, setRefundReject] = useState<PaymentRefund | null>(null)
  const [refundRejectReason, setRefundRejectReason] = useState('')
  const [remindChannel, setRemindChannel] = useState('')

  const status = payment ? workflowStatus(payment) : ''
  const channels = (payment?.reply_channels ?? []).filter(item => item !== 'website')

  const canSubmit =
    canChange && (status === 'pending' || status === 'proof_submitted' || status === 'rejected') && (payment?.attachment_count ?? 0) > 0

  return (
    <>
      <Sheet
        open={payment !== null}
        onOpenChange={open => {
          if (!open) onOpenChange(false)
        }}
      >
        <SheetContent className='overflow-y-auto sm:max-w-4xl'>
          <SheetHeader>
            <SheetTitle>{payment?.payment_number ?? 'Payment'} · Payment management</SheetTitle>
          </SheetHeader>
          {payment && (
            <div className='payment-print flex flex-col gap-5 px-4 pb-6'>
              <div className='flex flex-wrap items-center gap-2'>
                <Badge variant='outline' className={cn(payment.is_overdue && 'text-destructive')}>
                  {payment.status_label}
                </Badge>
                <Badge variant='outline'>{payment.balance?.account_status_label || 'Account'}</Badge>
                <Badge variant='outline'>{payment.payment_type_label}</Badge>
                <Badge variant='outline'>{payment.payment_method_label}</Badge>
              </div>
              <dl className='grid gap-3 text-sm sm:grid-cols-3'>
                <div>
                  <dt className='text-muted-foreground'>Customer</dt>
                  <dd className='font-medium'>
                    <button type='button' className='hover:underline' onClick={() => onCustomer(payment)}>
                      {payment.customer.name}
                    </button>
                  </dd>
                </div>
                <div>
                  <dt className='text-muted-foreground'>Reservation</dt>
                  <dd className='font-medium'>
                    <Link href={`/bookings/${payment.case.id}`} className='hover:underline'>
                      {payment.case.case_number}
                    </Link>
                  </dd>
                </div>
                <div>
                  <dt className='text-muted-foreground'>Property</dt>
                  <dd className='font-medium'>{payment.property?.name ?? '—'}</dd>
                </div>
                <div>
                  <dt className='text-muted-foreground'>Location</dt>
                  <dd className='font-medium'>{payment.location?.name ?? '—'}</dd>
                </div>
                <div>
                  <dt className='text-muted-foreground'>Stay</dt>
                  <dd className='font-medium'>
                    {formatDueAt(payment.check_in) || '—'} → {formatDueAt(payment.check_out) || '—'}
                  </dd>
                </div>
                <div>
                  <dt className='text-muted-foreground'>Balance due</dt>
                  <dd className='font-medium'>{payment.balance_labels?.outstanding || payment.balance?.outstanding || '—'}</dd>
                </div>
              </dl>
              <div className='grid gap-3 sm:grid-cols-4'>
                {[
                  ['Total charges', payment.balance_labels?.total_charges || payment.balance?.total_charges || payment.balance?.case_value],
                  ['Total paid', payment.balance_labels?.paid || payment.balance?.paid],
                  ['Total refunded', payment.balance_labels?.refunded || payment.balance?.refunded],
                  ['Balance due', payment.balance_labels?.outstanding || payment.balance?.outstanding]
                ].map(([label, value]) => (
                  <div key={label} className='rounded-md border p-3'>
                    <p className='text-muted-foreground text-xs'>{label}</p>
                    <p className='text-lg font-semibold'>{value || '—'}</p>
                  </div>
                ))}
              </div>
              <div className='flex flex-wrap gap-2'>
                {can(['payments.create_payment', 'payments.change_payment']) && (
                  <Button type='button' size='sm' onClick={() => setAction('payment')}>
                    Add payment
                  </Button>
                )}
                {can(['payments.add_charge', 'payments.change_payment']) && (
                  <Button type='button' size='sm' variant='outline' onClick={() => setAction('charge')}>
                    Add charge
                  </Button>
                )}
                {can(['payments.add_penalty', 'payments.change_payment']) && (
                  <Button type='button' size='sm' variant='outline' onClick={() => setAction('penalty')}>
                    Add penalty
                  </Button>
                )}
                {canRequestRefund && (
                  <Button type='button' size='sm' variant='outline' onClick={() => setAction('refund')}>
                    Refund
                  </Button>
                )}
                <Button type='button' size='sm' variant='ghost' onClick={() => window.print()}>
                  Print
                </Button>
              </div>
              <dl className='grid gap-3 text-sm sm:grid-cols-2'>
                <div>
                  <dt className='text-muted-foreground'>Type</dt>
                  <dd className='font-medium'>{payment.payment_type_label}</dd>
                </div>
                <div>
                  <dt className='text-muted-foreground'>Amount</dt>
                  <dd className='font-medium'>{payment.amount_label}</dd>
                </div>
                <div>
                  <dt className='text-muted-foreground'>Currency</dt>
                  <dd className='font-medium'>{payment.currency}</dd>
                </div>
                <div>
                  <dt className='text-muted-foreground'>Payment Method</dt>
                  <dd className='font-medium'>{payment.payment_method_label}</dd>
                </div>
                <div>
                  <dt className='text-muted-foreground'>Expected Date</dt>
                  <dd className={cn('font-medium', payment.is_overdue && 'text-destructive')}>
                    {payment.is_overdue ? `Overdue · Expected ${formatDueAt(payment.expected_date) || '—'}` : formatDueAt(payment.expected_date) || '—'}
                  </dd>
                </div>
                <div>
                  <dt className='text-muted-foreground'>Paid Date</dt>
                  <dd className='font-medium'>{formatDueAt(payment.paid_at) || '—'}</dd>
                </div>
                <div>
                  <dt className='text-muted-foreground'>Status</dt>
                  <dd className='font-medium'>{payment.status_label}</dd>
                </div>
                <div>
                  <dt className='text-muted-foreground'>Created By</dt>
                  <dd className='font-medium'>{payment.created_by?.display_name || payment.created_by?.name || '—'}</dd>
                </div>
                <div>
                  <dt className='text-muted-foreground'>Created Date</dt>
                  <dd className='font-medium'>{formatRelativeTime(payment.created_at) || '—'}</dd>
                </div>
                <div>
                  <dt className='text-muted-foreground'>Approved By</dt>
                  <dd className='font-medium'>{payment.approved_by?.display_name || payment.approved_by?.name || '—'}</dd>
                </div>
                <div>
                  <dt className='text-muted-foreground'>Approved Date</dt>
                  <dd className='font-medium'>{formatDueAt(payment.approved_at) || '—'}</dd>
                </div>
              </dl>
              {payment.notes && <p className='text-sm whitespace-pre-wrap'>{payment.notes}</p>}
              <section>
                <h3 className='mb-2 text-sm font-semibold tracking-wide uppercase'>Transaction history</h3>
                {(payment.ledger ?? []).length === 0 ? (
                  <p className='text-muted-foreground text-sm'>No ledger rows yet.</p>
                ) : (
                  <div className='overflow-x-auto'>
                    <table className='w-full text-sm'>
                      <thead>
                        <tr className='text-muted-foreground text-left'>
                          <th className='pb-2 pr-3 font-medium'>Date</th>
                          <th className='pb-2 pr-3 font-medium'>Type</th>
                          <th className='pb-2 pr-3 font-medium'>Description</th>
                          <th className='pb-2 pr-3 text-right font-medium'>Amount</th>
                          <th className='pb-2 pr-3 font-medium'>Method</th>
                          <th className='pb-2 pr-3 font-medium'>Status</th>
                          <th className='pb-2 pr-3 font-medium'>By</th>
                          <th className='pb-2 pr-3 font-medium'>Reference</th>
                          <th className='pb-2 pr-3 font-medium'>Notes</th>
                          <th className='pb-2 font-medium'>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {payment.ledger?.map(row => (
                          <tr key={row.id} className='border-t'>
                            <td className='py-2 pr-3'>{formatDueAt(row.occurred_at) || '—'}</td>
                            <td className='py-2 pr-3'>{row.type_label}</td>
                            <td className='py-2 pr-3'>
                              {row.description}
                              {row.reason ? <span className='text-muted-foreground'> · {row.reason}</span> : null}
                            </td>
                            <td className={cn('py-2 pr-3 text-right font-medium', Number(row.signed_amount) < 0 && 'text-emerald-700')}>
                              {Number(row.signed_amount) > 0 ? '+' : ''}
                              {row.signed_amount}
                            </td>
                            <td className='py-2 pr-3'>{row.method_label || '—'}</td>
                            <td className='py-2 pr-3'>{row.status_label}</td>
                            <td className='py-2 pr-3'>{row.created_by?.display_name || row.created_by?.name || '—'}</td>
                            <td className='py-2 pr-3'>{row.reference || '—'}</td>
                            <td className='py-2 pr-3'>{row.notes || '—'}</td>
                            <td className='py-2'>
                              {row.voidable && can('payments.void_charge') ? (
                                <Button
                                  type='button'
                                  size='sm'
                                  variant='ghost'
                                  onClick={() => {
                                    setVoidSourceId(row.source_id)
                                    setAction('void')
                                  }}
                                >
                                  Void
                                </Button>
                              ) : (
                                <span className='text-muted-foreground'>—</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
              {payment.rejection_reason && (
                <p className='text-destructive text-sm'>Rejected: {payment.rejection_reason}</p>
              )}
              <div className='flex flex-wrap gap-2'>
                {canSubmit && (
                  <Button type='button' size='sm' onClick={() => onSubmit(payment)}>
                    Submit for approval
                  </Button>
                )}
                {status === 'pending_approval' && canApprove && (
                  <Button type='button' size='sm' onClick={() => onApprove(payment)}>
                    Approve
                  </Button>
                )}
                {status === 'pending_approval' && canReject && (
                  <Button type='button' size='sm' variant='outline' onClick={() => setRejectOpen(true)}>
                    Reject
                  </Button>
                )}
                {canRemind && (
                  <div className='flex flex-wrap items-center gap-2'>
                    {channels.length > 1 && (
                      <Select value={remindChannel || channels[0]} onValueChange={value => value && setRemindChannel(value)}>
                        <SelectTrigger className='w-52'>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {channels.map(channel => (
                            <SelectItem key={channel} value={channel}>
                              {channelLabel(channel)}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                    <Button
                      type='button'
                      size='sm'
                      variant='outline'
                      disabled={channels.length === 0}
                      onClick={() => onRemind(payment, remindChannel || channels[0])}
                    >
                      Send Payment Reminder
                    </Button>
                  </div>
                )}
                {status === 'approved' && canRequestRefund && Number(payment.refundable_amount || 0) > 0 && (
                  <Button type='button' size='sm' variant='outline' onClick={() => setRefundOpen(true)}>
                    Request Refund
                  </Button>
                )}
              </div>
              <section>
                <h3 className='mb-2 text-sm font-semibold tracking-wide uppercase'>Payment Attachments</h3>
                {canChange && status !== 'approved' && status !== 'cancelled' && (
                  <Input
                    type='file'
                    className='mb-3'
                    onChange={event => {
                      const next = event.target.files?.[0]

                      if (next) onUpload(payment, next)
                      event.target.value = ''
                    }}
                  />
                )}
                {(payment.attachments ?? []).length === 0 ? (
                  <p className='text-muted-foreground text-sm'>No attachments yet.</p>
                ) : (
                  <ul className='space-y-3'>
                    {payment.attachments?.map(item => (
                      <li key={item.id} className='rounded-md border p-3'>
                        {item.is_image ? (
                          <img src={item.url} alt={item.original_name} className='mb-2 max-h-48 rounded-md object-contain' />
                        ) : null}
                        <a href={item.url} target='_blank' rel='noreferrer' className='text-sm font-medium hover:underline'>
                          {item.original_name || 'Open attachment'}
                        </a>
                        {item.description && <p className='text-muted-foreground text-xs'>{item.description}</p>}
                      </li>
                    ))}
                  </ul>
                )}
              </section>
              <section>
                <h3 className='mb-2 text-sm font-semibold tracking-wide uppercase'>Refunds</h3>
                {(payment.refunds ?? []).length === 0 ? (
                  <p className='text-muted-foreground text-sm'>No refunds.</p>
                ) : (
                  <ul className='space-y-3'>
                    {payment.refunds?.map(refund => (
                      <li key={refund.id} className='rounded-md border p-3 text-sm'>
                        <p className='font-medium'>
                          {refund.refund_number} · {refund.amount_label} · {refund.status_label}
                        </p>
                        {refund.reason && <p className='text-muted-foreground mt-1'>{refund.reason}</p>}
                        {refund.status === 'pending_approval' && canManageRefund && (
                          <div className='mt-2 flex gap-2'>
                            <Button type='button' size='sm' onClick={() => onApproveRefund(refund)}>
                              Approve Refund
                            </Button>
                            <Button type='button' size='sm' variant='outline' onClick={() => setRefundReject(refund)}>
                              Reject Refund
                            </Button>
                          </div>
                        )}
                        {refund.status === 'approved' && canManageRefund && (
                          <Button type='button' size='sm' className='mt-2' onClick={() => onCompleteRefund(refund)}>
                            Mark refunded
                          </Button>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </div>
          )}
        </SheetContent>
      </Sheet>

      <Dialog open={rejectOpen} onOpenChange={open => !open && setRejectOpen(false)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reject payment</DialogTitle>
          </DialogHeader>
          <FieldGroup>
            <Field>
              <FieldLabel>Reason</FieldLabel>
              <Textarea value={rejectReason} onChange={event => setRejectReason(event.target.value)} rows={3} />
            </Field>
          </FieldGroup>
          <DialogFooter>
            <Button type='button' variant='ghost' onClick={() => setRejectOpen(false)}>
              Cancel
            </Button>
            <Button
              type='button'
              disabled={!rejectReason.trim() || !payment}
              onClick={() => {
                if (!payment) return
                onReject(payment, rejectReason.trim())
                setRejectOpen(false)
                setRejectReason('')
              }}
            >
              Reject
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={refundOpen} onOpenChange={open => !open && setRefundOpen(false)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Request refund</DialogTitle>
          </DialogHeader>
          <FieldGroup>
            <Field>
              <FieldLabel>Refund Amount</FieldLabel>
              <Input value={refundAmount} onChange={event => setRefundAmount(event.target.value)} placeholder={payment?.refundable_amount ?? ''} />
            </Field>
            <Field>
              <FieldLabel>Reason</FieldLabel>
              <Textarea value={refundReason} onChange={event => setRefundReason(event.target.value)} rows={3} />
            </Field>
          </FieldGroup>
          <DialogFooter>
            <Button type='button' variant='ghost' onClick={() => setRefundOpen(false)}>
              Cancel
            </Button>
            <Button
              type='button'
                disabled={!refundAmount.trim() || !refundReason.trim() || !payment}
              onClick={() => {
                if (!payment) return
                onRequestRefund(payment, refundAmount.trim(), refundReason.trim())
                setRefundOpen(false)
                setRefundAmount('')
                setRefundReason('')
              }}
            >
              Request refund
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {payment && (
        <PaymentManagementDialogs
          payment={payment}
          action={action}
          canReceive={can('payments.verify_payment')}
          canCompleteRefund={canManageRefund}
          voidSourceId={voidSourceId}
          onOpenChange={open => {
            if (!open) {
              setAction(null)
              setVoidSourceId(undefined)
            }
          }}
          onUpdated={next => onUpdated?.(next)}
        />
      )}

      <Dialog open={refundReject !== null} onOpenChange={open => !open && setRefundReject(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reject refund</DialogTitle>
          </DialogHeader>
          <FieldGroup>
            <Field>
              <FieldLabel>Reason</FieldLabel>
              <Textarea value={refundRejectReason} onChange={event => setRefundRejectReason(event.target.value)} rows={3} />
            </Field>
          </FieldGroup>
          <DialogFooter>
            <Button type='button' variant='ghost' onClick={() => setRefundReject(null)}>
              Cancel
            </Button>
            <Button
              type='button'
              disabled={!refundRejectReason.trim() || !refundReject}
              onClick={() => {
                if (!refundReject) return
                onRejectRefund(refundReject, refundRejectReason.trim())
                setRefundReject(null)
                setRefundRejectReason('')
              }}
            >
              Reject refund
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

export default PaymentDetailSheet
