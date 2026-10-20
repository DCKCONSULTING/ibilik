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
import { formatDueLabel, formatRelativeTime } from '@/lib/datetime'
import { followUpsApi } from '@/lib/pipeline/api'
import type { CaseFollowUp, FollowUpListResponse, PipelineProperty, PipelineUser } from '@/lib/pipeline/types'
import { cn } from '@/lib/utils'
import CustomerDetailSheet from '@/views/crm/customers/customer-detail-sheet'
import CaseFollowUpDialog from '@/views/crm/pipeline/case-follow-up-dialog'

import FollowUpDetailSheet from './follow-up-detail-sheet'

const STATUS_OPTIONS = [
  { id: 'actionable', label: 'Pending + Overdue' },
  { id: 'all', label: 'All' },
  { id: 'pending', label: 'Pending' },
  { id: 'overdue', label: 'Overdue' },
  { id: 'completed', label: 'Completed' },
  { id: 'cancelled', label: 'Cancelled' }
]

const DUE_OPTIONS = [
  { id: 'all', label: 'All' },
  { id: 'today', label: 'Today' },
  { id: 'tomorrow', label: 'Tomorrow' },
  { id: 'this_week', label: 'This Week' },
  { id: 'overdue', label: 'Overdue' },
  { id: 'custom', label: 'Custom Range' }
]

const SORT_OPTIONS = [
  { id: 'due_at', label: 'Due date' },
  { id: '-due_at', label: 'Due date (newest)' },
  { id: 'created_at', label: 'Created date' },
  { id: '-created_at', label: 'Created date (newest)' },
  { id: 'updated_at', label: 'Updated date' },
  { id: '-updated_at', label: 'Updated date (newest)' }
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

const FollowUpsPageView = () => {
  const { can } = useAuth()
  const canChange = can(['opportunities.change_opportunity', 'cases.change_case'])
  const canViewUsers = can('users.view_user')
  const [status, setStatus] = useQueryState('status', parseAsString.withDefault('actionable').withOptions(queryOptions))
  const [staff, setStaff] = useQueryState('staff', parseAsString.withDefault('all').withOptions(queryOptions))
  const [property, setProperty] = useQueryState('property', parseAsString.withDefault('all').withOptions(queryOptions))
  const scopedProperty = useListPropertyQuery(property)
  const [type, setType] = useQueryState('type', parseAsString.withDefault('all').withOptions(queryOptions))
  const [stage, setStage] = useQueryState('stage', parseAsString.withDefault('all').withOptions(queryOptions))
  const [source, setSource] = useQueryState('source', parseAsString.withDefault('all').withOptions(queryOptions))
  const [due, setDue] = useQueryState('due', parseAsString.withDefault('all').withOptions(queryOptions))
  const [dueFrom, setDueFrom] = useQueryState('due_from', parseAsString.withDefault('').withOptions(queryOptions))
  const [dueTo, setDueTo] = useQueryState('due_to', parseAsString.withDefault('').withOptions(queryOptions))
  const [search, setSearch] = useQueryState('search', parseAsString.withDefault('').withOptions(queryOptions))
  const [ordering, setOrdering] = useQueryState('ordering', parseAsString.withDefault('due_at').withOptions(queryOptions))
  const [page, setPage] = useQueryState('page', parseAsInteger.withDefault(1).withOptions(queryOptions))
  const [items, setItems] = useState<CaseFollowUp[]>([])

  const [meta, setMeta] = useState<Pick<FollowUpListResponse, 'types' | 'stages' | 'sources' | 'staff' | 'properties' | 'actionable_count'>>({
    types: [],
    stages: [],
    sources: [],
    staff: [],
    properties: [],
    actionable_count: 0
  })

  const [count, setCount] = useState(0)
  const [pageSize, setPageSize] = useState(25)
  const [hasNext, setHasNext] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [errorStatus, setErrorStatus] = useState<number | null>(null)
  const [selected, setSelected] = useState<CaseFollowUp | null>(null)
  const [customer, setCustomer] = useState<Customer | null>(null)
  const [editorOpen, setEditorOpen] = useState(false)
  const [editing, setEditing] = useState<CaseFollowUp | null>(null)

  const filtersActive = useMemo(
    () =>
      status !== 'actionable' ||
      staff !== 'all' ||
      property !== 'all' ||
      type !== 'all' ||
      stage !== 'all' ||
      source !== 'all' ||
      due !== 'all' ||
      Boolean(search.trim()),
    [due, property, search, source, staff, stage, status, type]
  )

  const load = () => {
    setLoading(true)

    return followUpsApi
      .list({
        status,
        assigned_staff: staff !== 'all' ? staff : undefined,
        property: scopedProperty,
        type: type !== 'all' ? type : undefined,
        case_stage: stage !== 'all' ? stage : undefined,
        source: source !== 'all' ? source : undefined,
        due: due !== 'all' ? due : undefined,
        due_from: due === 'custom' && dueFrom ? dueFrom : undefined,
        due_to: due === 'custom' && dueTo ? dueTo : undefined,
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
        setMeta({
          types: payload.types,
          stages: payload.stages,
          sources: payload.sources,
          staff: payload.staff,
          properties: payload.properties,
          actionable_count: payload.actionable_count
        })
        setError(null)
        setErrorStatus(null)
      })
      .catch(err => {
        setItems([])
        setError(isApiError(err) ? err.message : 'Unable to load follow-ups.')
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
  }, [status, staff, property, type, stage, source, due, dueFrom, dueTo, search, ordering, page])

  const clearFilters = () => {
    void setStatus('actionable')
    void setStaff('all')
    void setProperty('all')
    void setType('all')
    void setStage('all')
    void setSource('all')
    void setDue('all')
    void setDueFrom('')
    void setDueTo('')
    void setSearch('')
    void setOrdering('due_at')
    void setPage(1)
  }

  const changeFilter = (setter: (value: string) => unknown, value: string | null) => {
    if (!value) return
    void setter(value)
    void setPage(1)
  }

  const customerFromFollowUp = (item: CaseFollowUp): Customer | null => {
    if (!item.customer) return null

    return {
      id: item.customer.id,
      name: item.customer.name,
      email: item.customer.email,
      phone: item.customer.phone,
      status: item.customer.status ?? 'lead',
      sources: [],
      properties: item.property ? [item.property] : [],
      last_contact_at: null,
      reply_channels: []
    }
  }

  const completeItem = async (item: CaseFollowUp) => {
    try {
      await followUpsApi.complete(item.id)
      toast.success('Follow-up completed.')
      setSelected(null)
      await load()
    } catch (err) {
      toast.error(isApiError(err) ? err.message : 'Unable to complete this follow-up.')
    }
  }

  const cancelItem = async (item: CaseFollowUp) => {
    try {
      await followUpsApi.cancel(item.id)
      toast.success('Follow-up cancelled.')
      setSelected(null)
      await load()
    } catch (err) {
      toast.error(isApiError(err) ? err.message : 'Unable to cancel this follow-up.')
    }
  }

  const start = count === 0 ? 0 : (page - 1) * pageSize + 1
  const end = Math.min(page * pageSize, count)

  const staffOptions = meta.staff.map((user: PipelineUser) => ({
    id: user.id,
    label: user.display_name || user.name || user.username
  }))

  return (
    <div className='flex flex-col gap-6'>
      <div className='flex flex-wrap items-start justify-between gap-3'>
        <div>
          <h1 className='text-2xl font-semibold'>Follow-ups</h1>
          <p className='text-muted-foreground text-sm'>
            Work queue for authorized case follow-ups. Pending and overdue items are shown by default.
          </p>
        </div>
        {canChange && (
          <Button
            onClick={() => {
              setEditing(null)
              setEditorOpen(true)
            }}
          >
            <PlusIcon />
            New Follow-up
          </Button>
        )}
      </div>

      {error && (
        <Alert variant='destructive'>
          <AlertTitle>{errorStatus === 403 ? 'Permission denied' : 'API error'}</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Card className='shadow-none'>
        <CardHeader className='gap-4'>
          <div className='flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between'>
            <div>
              <CardTitle>Follow-ups</CardTitle>
              <CardDescription>
                {meta.actionable_count} pending or overdue in your scope.
              </CardDescription>
            </div>
            <InputGroup className='lg:max-w-80'>
              <InputGroupAddon>
                <SearchIcon className='size-4' />
              </InputGroupAddon>
              <InputGroupInput
                type='search'
                placeholder='Search follow-ups...'
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
            <FilterSelect label='Assigned Staff' value={staff} onValueChange={value => changeFilter(setStaff, value)}>
              <SelectItem value='all'>All Staff</SelectItem>
              {meta.staff.map(user => (
                <SelectItem key={user.id} value={String(user.id)}>
                  {user.display_name || user.name || user.username}
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
            <FilterSelect label='Type' value={type} onValueChange={value => changeFilter(setType, value)}>
              <SelectItem value='all'>All Types</SelectItem>
              {meta.types.map(item => (
                <SelectItem key={item.id} value={item.id}>
                  {item.label}
                </SelectItem>
              ))}
            </FilterSelect>
            <FilterSelect label='Due Date' value={due} onValueChange={value => changeFilter(setDue, value)}>
              {DUE_OPTIONS.map(item => (
                <SelectItem key={item.id} value={item.id}>
                  {item.label}
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
            <FilterSelect label='Source' value={source} onValueChange={value => changeFilter(setSource, value)}>
              <SelectItem value='all'>All Sources</SelectItem>
              {meta.sources.map(item => (
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
          {loading && <p className='text-muted-foreground text-sm'>Loading follow-ups…</p>}
          {!loading && error && <p className='text-muted-foreground text-sm'>Follow-ups could not be loaded.</p>}
          {!loading && !error && items.length === 0 && (
            <div className='flex flex-col gap-3'>
              <p className='text-muted-foreground text-sm'>No follow-ups found</p>
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
                  <TableHead>Case</TableHead>
                  <TableHead>Customer</TableHead>
                  <TableHead>Follow-up</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Assigned Staff</TableHead>
                  <TableHead>Property</TableHead>
                  <TableHead>Due</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map(item => {
                  const pending = item.status === 'pending' || item.status === 'overdue'

                  return (
                    <TableRow key={item.id} className='cursor-pointer' onClick={() => setSelected(item)}>
                      <TableCell className='font-medium'>
                        {item.case ? (
                          <Link href={`/opportunities/${item.case.id}`} className='hover:underline' onClick={event => event.stopPropagation()}>
                            {item.case.case_number}
                          </Link>
                        ) : (
                          '—'
                        )}
                      </TableCell>
                      <TableCell>
                        {item.customer ? (
                          <button
                            type='button'
                            className='hover:underline'
                            onClick={event => {
                              event.stopPropagation()
                              setCustomer(customerFromFollowUp(item))
                            }}
                          >
                            {item.customer.name}
                          </button>
                        ) : (
                          '—'
                        )}
                      </TableCell>
                      <TableCell className='max-w-48 truncate font-medium'>{item.title}</TableCell>
                      <TableCell>{item.type_label}</TableCell>
                      <TableCell>{item.assigned_to?.display_name || item.assigned_to?.name || 'Unassigned'}</TableCell>
                      <TableCell>{item.property?.name ?? '—'}</TableCell>
                      <TableCell className={cn(item.status === 'overdue' && 'text-destructive font-medium')} title={item.due_at ?? undefined}>
                        {formatDueLabel(item.due_at, new Date(), item.status)}
                      </TableCell>
                      <TableCell className={cn(item.status === 'overdue' && 'text-destructive font-medium')}>{item.status_label}</TableCell>
                      <TableCell>{formatRelativeTime(item.created_at) || '—'}</TableCell>
                      <TableCell>
                        <div className='flex flex-wrap gap-1' onClick={event => event.stopPropagation()}>
                          {pending ? (
                            <>
                              <Button type='button' size='sm' variant='outline' disabled={!canChange} onClick={() => void completeItem(item)}>
                                Complete
                              </Button>
                              <Button
                                type='button'
                                size='sm'
                                variant='ghost'
                                disabled={!canChange}
                                onClick={() => {
                                  setEditing(item)
                                  setEditorOpen(true)
                                }}
                              >
                                Edit
                              </Button>
                              <Button type='button' size='sm' variant='ghost' disabled={!canChange} onClick={() => void cancelItem(item)}>
                                Cancel
                              </Button>
                            </>
                          ) : (
                            <Button type='button' size='sm' variant='ghost' onClick={() => setSelected(item)}>
                              View
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })}
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

      <FollowUpDetailSheet
        followUp={selected}
        canChange={canChange}
        onOpenChange={open => {
          if (!open) setSelected(null)
        }}
        onComplete={item => void completeItem(item)}
        onEdit={item => {
          setSelected(null)
          setEditing(item)
          setEditorOpen(true)
        }}
        onCancel={item => void cancelItem(item)}
        onCustomer={item => setCustomer(customerFromFollowUp(item))}
      />
      <CustomerDetailSheet
        customer={customer}
        onOpenChange={open => {
          if (!open) setCustomer(null)
        }}
      />
      <CaseFollowUpDialog
        key={editorOpen ? `${editing?.id ?? 'new'}` : 'closed'}
        open={editorOpen}
        allowCaseSelect={!editing}
        followUp={editing}
        types={meta.types.length > 0 ? meta.types : undefined}
        staffOptions={staffOptions}
        canViewUsers={canViewUsers}
        onOpenChange={open => {
          setEditorOpen(open)
          if (!open) setEditing(null)
        }}
        onSaved={() => {
          void load()
        }}
      />
    </div>
  )
}

export default FollowUpsPageView
