'use client'

import { useEffect, useMemo, useState, type ReactNode } from 'react'

import Link from 'next/link'
import { parseAsInteger, parseAsString, useQueryState } from 'nuqs'
import { PlusIcon, SearchIcon } from 'lucide-react'
import { toast } from 'sonner'

import { useAuth } from '@/components/auth/auth-provider'
import { useListPropertyQuery } from '@/components/properties/property-provider'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { InputGroup, InputGroupAddon, InputGroupInput } from '@/components/ui/input-group'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { isApiError } from '@/lib/api'
import type { Customer } from '@/lib/customers/types'
import { customersApi } from '@/lib/customers/api'
import { formatDueAt, formatRelativeTime } from '@/lib/datetime'
import { paymentsApi } from '@/lib/payments/api'
import type { Payment, PaymentListResponse, PaymentRefund, PaymentSummary } from '@/lib/payments/types'
import type { PipelineProperty, PipelineUser } from '@/lib/pipeline/types'
import { cn } from '@/lib/utils'
import CustomerDetailSheet from '@/views/crm/customers/customer-detail-sheet'

import PaymentDetailSheet from './payment-detail-sheet'
import PaymentFormDialog from './payment-form-dialog'

const STATUS_OPTIONS = [
  { id: 'all', label: 'All' },
  { id: 'pending', label: 'Pending' },
  { id: 'proof_submitted', label: 'Proof Submitted' },
  { id: 'pending_approval', label: 'Pending Approval' },
  { id: 'approved', label: 'Approved' },
  { id: 'rejected', label: 'Rejected' },
  { id: 'overdue', label: 'Overdue' },
  { id: 'cancelled', label: 'Cancelled' }
]

const DUE_OPTIONS = [
  { id: 'all', label: 'All' },
  { id: 'today', label: 'Today' },
  { id: 'tomorrow', label: 'Tomorrow' },
  { id: 'this_week', label: 'This Week' },
  { id: 'this_month', label: 'This Month' },
  { id: 'overdue', label: 'Overdue' },
  { id: 'custom', label: 'Custom Range' }
]

const DATE_FIELD_OPTIONS = [
  { id: 'expected_date', label: 'Expected Date' },
  { id: 'paid_at', label: 'Paid Date' },
  { id: 'created_at', label: 'Created Date' }
]

const SORT_OPTIONS = [
  { id: '-created_at', label: 'Created (newest)' },
  { id: 'created_at', label: 'Created (oldest)' },
  { id: 'expected_date', label: 'Expected date' },
  { id: '-expected_date', label: 'Expected date (newest)' },
  { id: '-amount', label: 'Amount (high)' },
  { id: 'amount', label: 'Amount (low)' }
]

const queryOptions = { history: 'replace' as const, clearOnDefault: true }
const FILTER_FIELD_CLASS = 'grid min-w-0 grid-cols-[8rem_minmax(0,1fr)] items-center gap-2'

const FilterSelect = ({
  label,
  value,
  onValueChange,
  children
}: {
  label: string
  value: string
  onValueChange: (value: string | null) => void
  children: ReactNode
}) => (
  <div className={FILTER_FIELD_CLASS}>
    <FieldLabel className='text-muted-foreground'>{label}</FieldLabel>
    <div className='min-w-0'>
      <Select value={value} onValueChange={onValueChange}>
        <SelectTrigger className='w-full min-w-0'>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>{children}</SelectContent>
      </Select>
    </div>
  </div>
)

const emptySummary = (): PaymentSummary => ({
  expected: '0',
  pending_approval: '0',
  approved: '0',
  deposits: '0',
  refunded: '0',
  expected_label: 'MYR 0',
  pending_approval_label: 'MYR 0',
  approved_label: 'MYR 0',
  deposits_label: 'MYR 0',
  refunded_label: 'MYR 0'
})

const PaymentsPageView = () => {
  const { can } = useAuth()
  const canCreate = can(['payments.create_payment', 'payments.change_payment'])
  const canChange = can('payments.change_payment')
  const canApprove = can('payments.verify_payment')
  const canReject = can(['payments.reject_payment', 'payments.verify_payment'])
  const canRemind = can(['payments.send_reminder', 'payments.change_payment'])
  const canRequestRefund = can(['payments.request_refund', 'payments.change_payment'])
  const canManageRefund = can(['payments.refund_payment', 'payments.verify_payment'])
  const [status, setStatus] = useQueryState('status', parseAsString.withDefault('all').withOptions(queryOptions))
  const [type, setType] = useQueryState('type', parseAsString.withDefault('all').withOptions(queryOptions))
  const [method, setMethod] = useQueryState('method', parseAsString.withDefault('all').withOptions(queryOptions))
  const [property, setProperty] = useQueryState('property', parseAsString.withDefault('all').withOptions(queryOptions))
  const scopedProperty = useListPropertyQuery(property)
  const [staff, setStaff] = useQueryState('staff', parseAsString.withDefault('all').withOptions(queryOptions))
  const [stage, setStage] = useQueryState('stage', parseAsString.withDefault('all').withOptions(queryOptions))
  const [customer, setCustomerFilter] = useQueryState('customer', parseAsString.withDefault('all').withOptions(queryOptions))
  const [dateField, setDateField] = useQueryState('date_field', parseAsString.withDefault('expected_date').withOptions(queryOptions))
  const [due, setDue] = useQueryState('due', parseAsString.withDefault('all').withOptions(queryOptions))
  const [dueFrom, setDueFrom] = useQueryState('date_from', parseAsString.withDefault('').withOptions(queryOptions))
  const [dueTo, setDueTo] = useQueryState('date_to', parseAsString.withDefault('').withOptions(queryOptions))
  const [search, setSearch] = useQueryState('search', parseAsString.withDefault('').withOptions(queryOptions))
  const [ordering, setOrdering] = useQueryState('ordering', parseAsString.withDefault('-created_at').withOptions(queryOptions))
  const [page, setPage] = useQueryState('page', parseAsInteger.withDefault(1).withOptions(queryOptions))

  const [items, setItems] = useState<Payment[]>([])
  const [summary, setSummary] = useState<PaymentSummary>(emptySummary())

  const [meta, setMeta] = useState<Pick<PaymentListResponse, 'types' | 'methods' | 'statuses' | 'stages' | 'staff' | 'properties'>>({
    types: [],
    methods: [],
    statuses: [],
    stages: [],
    staff: [],
    properties: []
  })

  const [customers, setCustomers] = useState<Customer[]>([])
  const [count, setCount] = useState(0)
  const [pageSize, setPageSize] = useState(25)
  const [hasNext, setHasNext] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [errorStatus, setErrorStatus] = useState<number | null>(null)
  const [selected, setSelected] = useState<Payment | null>(null)
  const [customerSheet, setCustomerSheet] = useState<Customer | null>(null)
  const [editorOpen, setEditorOpen] = useState(false)

  const filtersActive = useMemo(
    () =>
      status !== 'all' ||
      type !== 'all' ||
      method !== 'all' ||
      property !== 'all' ||
      staff !== 'all' ||
      stage !== 'all' ||
      customer !== 'all' ||
      due !== 'all' ||
      Boolean(search.trim()),
    [customer, due, method, property, search, staff, stage, status, type]
  )

  const load = () => {
    setLoading(true)

    return paymentsApi
      .list({
        status,
        payment_type: type !== 'all' ? type : undefined,
        payment_method: method !== 'all' ? method : undefined,
        property: scopedProperty,
        staff: staff !== 'all' ? staff : undefined,
        case_stage: stage !== 'all' ? stage : undefined,
        customer: customer !== 'all' ? customer : undefined,
        date_field: dateField,
        due: due !== 'all' ? due : undefined,
        date_from: due === 'custom' && dueFrom ? dueFrom : undefined,
        date_to: due === 'custom' && dueTo ? dueTo : undefined,
        search: search.trim() || undefined,
        ordering,
        page,
        page_size: 25
      })
      .then(payload => {
        setItems(payload.results)
        setCount(payload.count)
        setPageSize(payload.page_size)
        setHasNext(payload.has_next)
        setSummary(payload.summary)
        setMeta({
          types: payload.types,
          methods: payload.methods,
          statuses: payload.statuses,
          stages: payload.stages,
          staff: payload.staff,
          properties: payload.properties
        })
        setError(null)
        setErrorStatus(null)
      })
      .catch(err => {
        setItems([])
        setError(isApiError(err) ? err.message : 'Unable to load payments.')
        setErrorStatus(isApiError(err) ? err.status : 0)
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    const handle = window.setTimeout(() => {
      void load()
    }, 250)

    return () => window.clearTimeout(handle)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, type, method, property, staff, stage, customer, dateField, due, dueFrom, dueTo, search, ordering, page])

  useEffect(() => {
    customersApi
      .list({ page_size: 100 })
      .then(payload => setCustomers(payload.results))
      .catch(() => setCustomers([]))
  }, [])

  const clearFilters = () => {
    void setStatus('all')
    void setType('all')
    void setMethod('all')
    void setProperty('all')
    void setStaff('all')
    void setStage('all')
    void setCustomerFilter('all')
    void setDateField('expected_date')
    void setDue('all')
    void setDueFrom('')
    void setDueTo('')
    void setSearch('')
    void setOrdering('-created_at')
    void setPage(1)
  }

  const changeFilter = (setter: (value: string) => unknown, value: string | null) => {
    if (!value) return
    void setter(value)
    void setPage(1)
  }

  const customerFromPayment = (item: Payment): Customer => ({
    id: item.customer.id,
    name: item.customer.name,
    email: item.customer.email,
    phone: item.customer.phone,
    status: 'lead',
    sources: [],
    properties: item.property ? [item.property] : [],
    last_contact_at: null,
    reply_channels: []
  })

  const openDetail = async (item: Payment) => {
    try {
      setSelected(await paymentsApi.get(item.id))
    } catch (err) {
      toast.error(isApiError(err) ? err.message : 'Unable to load this payment.')
    }
  }

  const refreshSelected = async (id: number) => {
    const detail = await paymentsApi.get(id)

    setSelected(detail)
    await load()

    return detail
  }

  const start = count === 0 ? 0 : (page - 1) * pageSize + 1
  const end = Math.min(page * pageSize, count)

  return (
    <div className='flex flex-col gap-6'>
      <div className='flex flex-wrap items-start justify-between gap-3'>
        <div>
          <h1 className='text-2xl font-semibold'>Payments</h1>
          <p className='text-muted-foreground text-sm'>Review deposits, payment proofs, approvals, reminders, and refunds.</p>
        </div>
        {canCreate && (
          <Button onClick={() => setEditorOpen(true)}>
            <PlusIcon />
            New Payment
          </Button>
        )}
      </div>

      {error && (
        <Alert variant='destructive'>
          <AlertTitle>{errorStatus === 403 ? 'Permission denied' : 'API error'}</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className='grid gap-3 sm:grid-cols-2 xl:grid-cols-5'>
        {[
          { label: 'Expected', value: summary.expected_label },
          { label: 'Pending Approval', value: summary.pending_approval_label },
          { label: 'Approved', value: summary.approved_label },
          { label: 'Deposits', value: summary.deposits_label },
          { label: 'Refunded', value: summary.refunded_label }
        ].map(card => (
          <Card key={card.label} className='shadow-none'>
            <CardHeader className='pb-2'>
              <CardDescription>{card.label}</CardDescription>
              <CardTitle className='text-xl'>{card.value || 'MYR 0'}</CardTitle>
            </CardHeader>
          </Card>
        ))}
      </div>

      <Card className='shadow-none'>
        <CardHeader className='gap-4'>
          <div className='flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between'>
            <div>
              <CardTitle>Payments</CardTitle>
              <CardDescription>Work queue for authorized case payments.</CardDescription>
            </div>
            <InputGroup className='lg:max-w-80'>
              <InputGroupAddon>
                <SearchIcon className='size-4' />
              </InputGroupAddon>
              <InputGroupInput
                type='search'
                placeholder='Search payment, case, customer...'
                value={search}
                onChange={event => {
                  void setSearch(event.target.value)
                  void setPage(1)
                }}
              />
            </InputGroup>
          </div>
          <div className='grid gap-3 sm:grid-cols-2 xl:grid-cols-4'>
            <FilterSelect label='Status' value={status} onValueChange={value => changeFilter(setStatus, value)}>
              {STATUS_OPTIONS.map(item => (
                <SelectItem key={item.id} value={item.id}>
                  {item.label}
                </SelectItem>
              ))}
            </FilterSelect>
            <FilterSelect label='Payment Type' value={type} onValueChange={value => changeFilter(setType, value)}>
              <SelectItem value='all'>All Types</SelectItem>
              {meta.types.map(item => (
                <SelectItem key={item.id} value={item.id}>
                  {item.label}
                </SelectItem>
              ))}
            </FilterSelect>
            <FilterSelect label='Method' value={method} onValueChange={value => changeFilter(setMethod, value)}>
              <SelectItem value='all'>All Methods</SelectItem>
              {meta.methods.map(item => (
                <SelectItem key={item.id} value={item.id}>
                  {item.label}
                </SelectItem>
              ))}
            </FilterSelect>
            <FilterSelect label='Property' value={property} onValueChange={value => changeFilter(setProperty, value)}>
              <SelectItem value='all'>All Properties</SelectItem>
              {meta.properties.map((item: PipelineProperty) => (
                <SelectItem key={item.id} value={String(item.id)}>
                  {item.name}
                </SelectItem>
              ))}
            </FilterSelect>
            <FilterSelect label='Staff' value={staff} onValueChange={value => changeFilter(setStaff, value)}>
              <SelectItem value='all'>All Staff</SelectItem>
              {meta.staff.map((user: PipelineUser) => (
                <SelectItem key={user.id} value={String(user.id)}>
                  {user.display_name || user.name || user.username}
                </SelectItem>
              ))}
            </FilterSelect>
            <FilterSelect label='Case Stage' value={stage} onValueChange={value => changeFilter(setStage, value)}>
              <SelectItem value='all'>All Stages</SelectItem>
              {meta.stages.map(item => (
                <SelectItem key={item.id} value={item.id}>
                  {item.label}
                </SelectItem>
              ))}
            </FilterSelect>
            <FilterSelect label='Customer' value={customer} onValueChange={value => changeFilter(setCustomerFilter, value)}>
              <SelectItem value='all'>All Customers</SelectItem>
              {customers.map(item => (
                <SelectItem key={item.id} value={String(item.id)}>
                  {item.name}
                </SelectItem>
              ))}
            </FilterSelect>
            <FilterSelect label='Date Field' value={dateField} onValueChange={value => changeFilter(setDateField, value)}>
              {DATE_FIELD_OPTIONS.map(item => (
                <SelectItem key={item.id} value={item.id}>
                  {item.label}
                </SelectItem>
              ))}
            </FilterSelect>
            <FilterSelect label='Date' value={due} onValueChange={value => changeFilter(setDue, value)}>
              {DUE_OPTIONS.map(item => (
                <SelectItem key={item.id} value={item.id}>
                  {item.label}
                </SelectItem>
              ))}
            </FilterSelect>
            <FilterSelect label='Sort' value={ordering} onValueChange={value => changeFilter(setOrdering, value)}>
              {SORT_OPTIONS.map(item => (
                <SelectItem key={item.id} value={item.id}>
                  {item.label}
                </SelectItem>
              ))}
            </FilterSelect>
            {due === 'custom' && (
              <>
                <div className={FILTER_FIELD_CLASS}>
                  <FieldLabel className='text-muted-foreground'>From</FieldLabel>
                  <Input type='date' className='w-full min-w-0' value={dueFrom} onChange={event => changeFilter(setDueFrom, event.target.value)} />
                </div>
                <div className={FILTER_FIELD_CLASS}>
                  <FieldLabel className='text-muted-foreground'>To</FieldLabel>
                  <Input type='date' className='w-full min-w-0' value={dueTo} onChange={event => changeFilter(setDueTo, event.target.value)} />
                </div>
              </>
            )}
          </div>
        </CardHeader>
        <CardContent className='overflow-x-auto'>
          {loading && <p className='text-muted-foreground text-sm'>Loading payments…</p>}
          {!loading && error && <p className='text-muted-foreground text-sm'>Payments could not be loaded.</p>}
          {!loading && !error && items.length === 0 && (
            <div className='flex flex-col gap-3'>
              <p className='text-muted-foreground text-sm'>No payments found</p>
              {filtersActive && (
                <Button type='button' variant='outline' className='w-fit' onClick={clearFilters}>
                  Clear filters
                </Button>
              )}
            </div>
          )}
          {!loading && !error && items.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Payment</TableHead>
                  <TableHead>Case</TableHead>
                  <TableHead>Customer</TableHead>
                  <TableHead>Property</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Method</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Expected Date</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map(item => (
                  <TableRow key={item.id} className='cursor-pointer' onClick={() => void openDetail(item)}>
                    <TableCell className='font-medium'>{item.payment_number}</TableCell>
                    <TableCell>
                      <Link href={`/opportunities/${item.case.id}`} className='hover:underline' onClick={event => event.stopPropagation()}>
                        {item.case.case_number}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <button
                        type='button'
                        className='hover:underline'
                        onClick={event => {
                          event.stopPropagation()
                          setCustomerSheet(customerFromPayment(item))
                        }}
                      >
                        {item.customer.name}
                      </button>
                    </TableCell>
                    <TableCell>{item.property?.name ?? '—'}</TableCell>
                    <TableCell>{item.payment_type_label}</TableCell>
                    <TableCell>{item.amount_label}</TableCell>
                    <TableCell>{item.payment_method_label}</TableCell>
                    <TableCell className={cn(item.is_overdue && 'text-destructive font-medium')}>{item.status_label}</TableCell>
                    <TableCell className={cn(item.is_overdue && 'text-destructive font-medium')}>
                      {item.is_overdue ? `Overdue · ${formatDueAt(item.expected_date)}` : formatDueAt(item.expected_date) || '—'}
                    </TableCell>
                    <TableCell>{formatRelativeTime(item.created_at) || '—'}</TableCell>
                    <TableCell>
                      <div className='flex flex-wrap gap-1' onClick={event => event.stopPropagation()}>
                        <Button type='button' size='sm' variant='ghost' onClick={() => void openDetail(item)}>
                          View
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          {!loading && !error && count > 0 && (
            <div className='mt-4 flex flex-wrap items-center justify-between gap-2'>
              <p className='text-muted-foreground text-sm'>
                {start}–{end} of {count}
              </p>
              <div className='flex gap-2'>
                <Button variant='outline' size='sm' disabled={page === 1} onClick={() => void setPage(Math.max(1, page - 1))}>
                  Previous
                </Button>
                <Button variant='outline' size='sm' disabled={!hasNext} onClick={() => void setPage(page + 1)}>
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

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
        onCustomer={item => setCustomerSheet(customerFromPayment(item))}
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
        onApproveRefund={async (refund: PaymentRefund) => {
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
      <CustomerDetailSheet
        customer={customerSheet}
        onOpenChange={open => {
          if (!open) setCustomerSheet(null)
        }}
      />
      <PaymentFormDialog
        key={editorOpen ? 'open' : 'closed'}
        open={editorOpen}
        allowCaseSelect
        types={meta.types}
        methods={meta.methods}
        onOpenChange={setEditorOpen}
        onSaved={() => {
          void load()
        }}
      />
    </div>
  )
}

export default PaymentsPageView
