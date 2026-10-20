'use client'

import { useEffect, useState } from 'react'

import { toast } from 'sonner'

import { useAuth } from '@/components/auth/auth-provider'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { isApiError } from '@/lib/api'
import { formatDueAt } from '@/lib/datetime'
import { paymentsApi } from '@/lib/payments/api'
import type { Payment, PaymentBalance, PaymentListResponse } from '@/lib/payments/types'
import type { Opportunity } from '@/lib/pipeline/types'
import { formatPipelineValue } from '@/lib/pipeline/validation'
import { cn } from '@/lib/utils'

import PaymentDetailSheet from './payment-detail-sheet'
import PaymentFormDialog from './payment-form-dialog'

const money = (value?: string | null) => formatPipelineValue(value) || 'MYR 0'

type CasePaymentsSectionProps = {
  opportunity: Opportunity
  types?: { id: string; label: string }[]
  methods?: { id: string; label: string }[]
}

const CasePaymentsSection = ({ opportunity, types, methods }: CasePaymentsSectionProps) => {
  const { can } = useAuth()
  const canCreate = can(['payments.create_payment', 'payments.change_payment'])
  const canChange = can('payments.change_payment')
  const canApprove = can('payments.verify_payment')
  const canReject = can(['payments.reject_payment', 'payments.verify_payment'])
  const canRemind = can(['payments.send_reminder', 'payments.change_payment'])
  const canRequestRefund = can(['payments.request_refund', 'payments.change_payment'])
  const canManageRefund = can(['payments.refund_payment', 'payments.verify_payment'])
  const [items, setItems] = useState<Payment[]>([])
  const [balance, setBalance] = useState<PaymentBalance | null>(null)
  const [meta, setMeta] = useState<Pick<PaymentListResponse, 'types' | 'methods'>>({ types: [], methods: [] })
  const [selected, setSelected] = useState<Payment | null>(null)
  const [editorOpen, setEditorOpen] = useState(false)

  const load = () =>
    paymentsApi
      .list({ case: opportunity.id, page_size: 100, status: 'all' })
      .then(payload => {
        setItems(payload.results)
        setBalance(payload.balance ?? null)
        setMeta({ types: payload.types, methods: payload.methods })
      })
      .catch(err => {
        toast.error(isApiError(err) ? err.message : 'Unable to load payments.')
      })

  useEffect(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opportunity.id])

  const refreshSelected = async (id: number) => {
    const detail = await paymentsApi.get(id)

    setSelected(detail)
    await load()

    return detail
  }

  return (
    <section className='bg-card rounded-xl border p-5'>
      <div className='mb-3 flex flex-wrap items-center justify-between gap-2'>
        <h2 className='text-sm font-semibold tracking-wide uppercase'>Payments</h2>
        <Button type='button' size='sm' disabled={!canCreate} onClick={() => setEditorOpen(true)}>
          + Add Payment
        </Button>
      </div>
      <dl className='mb-4 grid gap-3 text-sm sm:grid-cols-4'>
        <div>
          <dt className='text-muted-foreground'>Total charges</dt>
          <dd className='font-medium'>{money(balance?.total_charges ?? balance?.case_value ?? opportunity.value)}</dd>
        </div>
        <div>
          <dt className='text-muted-foreground'>Paid</dt>
          <dd className='font-medium'>{money(balance?.paid)}</dd>
        </div>
        <div>
          <dt className='text-muted-foreground'>Refunded</dt>
          <dd className='font-medium'>{money(balance?.refunded)}</dd>
        </div>
        <div>
          <dt className='text-muted-foreground'>Remaining</dt>
          <dd className='font-medium'>{money(balance?.outstanding)}</dd>
        </div>
      </dl>
      {items.length === 0 ? (
        <p className='text-muted-foreground text-sm'>No payments yet.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Payment</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Amount</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Expected</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map(item => (
              <TableRow key={item.id} className='cursor-pointer' onClick={() => void paymentsApi.get(item.id).then(setSelected)}>
                <TableCell className='font-medium'>{item.payment_number}</TableCell>
                <TableCell>{item.payment_type_label}</TableCell>
                <TableCell>{item.amount_label}</TableCell>
                <TableCell className={cn(item.is_overdue && 'text-destructive font-medium')}>{item.status_label}</TableCell>
                <TableCell>{formatDueAt(item.expected_date) || '—'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      <PaymentFormDialog
        key={editorOpen ? 'open' : 'closed'}
        open={editorOpen}
        caseRecord={opportunity}
        types={types ?? meta.types}
        methods={methods ?? meta.methods}
        onOpenChange={setEditorOpen}
        onSaved={() => void load()}
      />
      <PaymentDetailSheet
        payment={selected}
        canChange={canChange}
        canApprove={canApprove}
        canReject={canReject}
        canRemind={canRemind}
        canRequestRefund={canRequestRefund}
        canManageRefund={canManageRefund}
        onOpenChange={open => {
          if (!open) setSelected(null)
        }}
        onCustomer={() => undefined}
        onSubmit={async item => {
          try {
            await paymentsApi.submit(item.id)
            toast.success('Payment submitted for approval.')
            await refreshSelected(item.id)
          } catch (err) {
            toast.error(isApiError(err) ? err.message : 'Unable to submit this payment.')
          }
        }}
        onApprove={async item => {
          try {
            await paymentsApi.approve(item.id)
            toast.success('Payment approved.')
            await refreshSelected(item.id)
          } catch (err) {
            toast.error(isApiError(err) ? err.message : 'Unable to approve this payment.')
          }
        }}
        onReject={async (item, reason) => {
          try {
            await paymentsApi.reject(item.id, reason)
            toast.success('Payment rejected.')
            await refreshSelected(item.id)
          } catch (err) {
            toast.error(isApiError(err) ? err.message : 'Unable to reject this payment.')
          }
        }}
        onRemind={async (item, channel) => {
          try {
            await paymentsApi.sendReminder(item.id, { channel })
            toast.success('Payment reminder sent.')
            await refreshSelected(item.id)
          } catch (err) {
            toast.error(isApiError(err) ? err.message : 'Reminder failed.')
          }
        }}
        onUpload={async (item, file) => {
          try {
            await paymentsApi.uploadAttachment(item.id, file)
            toast.success('Payment proof uploaded.')
            await refreshSelected(item.id)
          } catch (err) {
            toast.error(isApiError(err) ? err.message : 'Unable to upload this attachment.')
          }
        }}
        onRequestRefund={async (item, amount, reason) => {
          try {
            await paymentsApi.requestRefund(item.id, { amount, reason })
            toast.success('Refund requested.')
            await refreshSelected(item.id)
          } catch (err) {
            toast.error(isApiError(err) ? err.message : 'Unable to request this refund.')
          }
        }}
        onApproveRefund={async refund => {
          try {
            await paymentsApi.approveRefund(refund.id)
            toast.success('Refund approved.')
            if (selected) await refreshSelected(selected.id)
          } catch (err) {
            toast.error(isApiError(err) ? err.message : 'Unable to approve this refund.')
          }
        }}
        onRejectRefund={async (refund, reason) => {
          try {
            await paymentsApi.rejectRefund(refund.id, reason)
            toast.success('Refund rejected.')
            if (selected) await refreshSelected(selected.id)
          } catch (err) {
            toast.error(isApiError(err) ? err.message : 'Unable to reject this refund.')
          }
        }}
        onUpdated={item => {
          setSelected(item)
          void load()
        }}
        onCompleteRefund={async refund => {
          try {
            await paymentsApi.completeRefund(refund.id)
            toast.success('Refund completed.')
            if (selected) await refreshSelected(selected.id)
          } catch (err) {
            toast.error(isApiError(err) ? err.message : 'Unable to complete this refund.')
          }
        }}
      />
    </section>
  )
}

export default CasePaymentsSection
