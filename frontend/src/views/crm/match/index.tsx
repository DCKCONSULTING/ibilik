'use client'

import { useEffect, useMemo, useState, type ReactNode } from 'react'

import Link from 'next/link'
import { parseAsInteger, parseAsString, useQueryState } from 'nuqs'
import { RefreshCwIcon, SearchIcon } from 'lucide-react'
import { toast } from 'sonner'

import { useAuth } from '@/components/auth/auth-provider'
import { useListPropertyQuery } from '@/components/properties/property-provider'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { InputGroup, InputGroupAddon, InputGroupInput } from '@/components/ui/input-group'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { isApiError } from '@/lib/api'
import type { Customer } from '@/lib/customers/types'
import { formatDueAt, formatRelativeTime } from '@/lib/datetime'
import { matchApi } from '@/lib/match/api'
import { assignmentBadgeLabel, emptyMatchSummary, isHighlightedRequest, relatedRecordHref, staffLabel } from '@/lib/match/display'
import type { MatchListResponse, MatchRequest, MatchSettings, MatchSummary, MatchWorkloadRow } from '@/lib/match/types'
import type { PipelineProperty } from '@/lib/pipeline/types'
import { cn } from '@/lib/utils'
import CustomerDetailSheet from '@/views/crm/customers/customer-detail-sheet'

import MatchDetailSheet from './match-detail-sheet'

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

const MatchPageView = () => {
  const { can } = useAuth()
  const canAssign = can('match.assign_request')
  const canReassign = can('match.reassign_request')
  const canUnassign = can('match.unassign_request')
  const canChangeStatus = can('match.change_status')
  const canChangePriority = can('match.change_priority')
  const canAddNotes = can('match.add_notes')
  const canResolve = can('match.resolve_request')
  const [status, setStatus] = useQueryState('status', parseAsString.withDefault('all').withOptions(queryOptions))
  const [type, setType] = useQueryState('type', parseAsString.withDefault('all').withOptions(queryOptions))
  const [priority, setPriority] = useQueryState('priority', parseAsString.withDefault('all').withOptions(queryOptions))
  const [property, setProperty] = useQueryState('property', parseAsString.withDefault('all').withOptions(queryOptions))
  const scopedProperty = useListPropertyQuery(property)
  const [staff, setStaff] = useQueryState('staff', parseAsString.withDefault('all').withOptions(queryOptions))
  const [unassignedOnly, setUnassignedOnly] = useQueryState(
    'unassigned',
    parseAsString.withDefault('0').withOptions(queryOptions)
  )
  const [due, setDue] = useQueryState('due', parseAsString.withDefault('all').withOptions(queryOptions))
  const [dueFrom, setDueFrom] = useQueryState('date_from', parseAsString.withDefault('').withOptions(queryOptions))
  const [dueTo, setDueTo] = useQueryState('date_to', parseAsString.withDefault('').withOptions(queryOptions))
  const [search, setSearch] = useQueryState('search', parseAsString.withDefault('').withOptions(queryOptions))
  const [ordering, setOrdering] = useQueryState('ordering', parseAsString.withDefault('-created_at').withOptions(queryOptions))
  const [page, setPage] = useQueryState('page', parseAsInteger.withDefault(1).withOptions(queryOptions))

  const [items, setItems] = useState<MatchRequest[]>([])
  const [summary, setSummary] = useState<MatchSummary>(emptyMatchSummary())
  const [meta, setMeta] = useState<Pick<MatchListResponse, 'statuses' | 'types' | 'priorities' | 'staff' | 'properties'>>({
    statuses: [],
    types: [],
    priorities: [],
    staff: [],
    properties: []
  })
  const [count, setCount] = useState(0)
  const [pageSize, setPageSize] = useState(25)
  const [hasNext, setHasNext] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [errorStatus, setErrorStatus] = useState<number | null>(null)
  const [selected, setSelected] = useState<MatchRequest | null>(null)
  const [customer, setCustomer] = useState<Customer | null>(null)
  const [assigning, setAssigning] = useState(false)
  const [settings, setSettings] = useState<MatchSettings | null>(null)
  const [savingSettings, setSavingSettings] = useState(false)
  const [workload, setWorkload] = useState<MatchWorkloadRow[]>([])

  const filtersActive = useMemo(
    () =>
      status !== 'all' ||
      type !== 'all' ||
      priority !== 'all' ||
      property !== 'all' ||
      staff !== 'all' ||
      unassignedOnly === '1' ||
      due !== 'all' ||
      Boolean(search.trim()),
    [due, priority, property, search, staff, status, type, unassignedOnly]
  )

  const load = () => {
    setLoading(true)

    return Promise.all([
      matchApi.list({
        status: status !== 'all' ? status : undefined,
        type: type !== 'all' ? type : undefined,
        priority: priority !== 'all' ? priority : undefined,
        property: scopedProperty,
        assigned_staff: staff !== 'all' ? staff : undefined,
        unassigned_only: unassignedOnly === '1' ? '1' : undefined,
        due: due !== 'all' ? due : undefined,
        date_from: due === 'custom' && dueFrom ? dueFrom : undefined,
        date_to: due === 'custom' && dueTo ? dueTo : undefined,
        search: search.trim() || undefined,
        ordering,
        page,
        page_size: 25
      }),
      matchApi.settings().catch(() => null),
      matchApi.workload(scopedProperty).catch(() => ({ results: [] as MatchWorkloadRow[] }))
    ])
      .then(([payload, nextSettings, nextWorkload]) => {
        setItems(payload.results)
        setCount(payload.count)
        setPageSize(payload.page_size)
        setHasNext(payload.has_next)
        setSummary(payload.summary)
        setMeta({
          statuses: payload.statuses,
          types: payload.types,
          priorities: payload.priorities,
          staff: payload.staff,
          properties: payload.properties
        })
        if (nextSettings) setSettings(nextSettings)
        setWorkload(nextWorkload.results)
        setError(null)
        setErrorStatus(null)
      })
      .catch(err => {
        setItems([])
        setError(isApiError(err) ? err.message : 'Unable to load Match requests.')
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
  }, [status, type, priority, property, staff, unassignedOnly, due, dueFrom, dueTo, search, ordering, page])

  const clearFilters = () => {
    void setStatus('all')
    void setType('all')
    void setPriority('all')
    void setProperty('all')
    void setStaff('all')
    void setUnassignedOnly('0')
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

  const customerFromRequest = (item: MatchRequest): Customer | null => {
    if (!item.customer) return null

    return {
      id: item.customer.id,
      name: item.customer.name,
      email: item.customer.email,
      phone: item.customer.phone,
      status: (item.customer.status as Customer['status']) ?? 'lead',
      sources: [],
      properties: item.property ? [item.property] : [],
      last_contact_at: null,
      reply_channels: []
    }
  }

  const openDetail = async (item: MatchRequest) => {
    try {
      setSelected(await matchApi.get(item.id))
    } catch (err) {
      toast.error(isApiError(err) ? err.message : 'Unable to load this request.')
    }
  }

  const runAction = async (action: () => Promise<MatchRequest>, success: string, failure: string) => {
    setAssigning(true)

    try {
      const result = await action()

      toast.success(success)
      setSelected(result)
      await load()
    } catch (err) {
      toast.error(isApiError(err) ? err.message : failure)
    } finally {
      setAssigning(false)
    }
  }

  const saveSetting = async (payload: Partial<Pick<MatchSettings, 'auto_assign_enabled' | 'property_staff_only' | 'org_wide_when_no_property'>>) => {
    if (!canAssign) return
    setSavingSettings(true)
    try {
      setSettings(await matchApi.updateSettings(payload))
      toast.success('Match settings updated.')
      await load()
    } catch (err) {
      toast.error(isApiError(err) ? err.message : 'Unable to update Match settings.')
    } finally {
      setSavingSettings(false)
    }
  }

  const start = count === 0 ? 0 : (page - 1) * pageSize + 1
  const end = Math.min(page * pageSize, count)

  return (
    <div className='flex flex-col gap-6'>
      <div className='flex flex-wrap items-start justify-between gap-3'>
        <div>
          <h1 className='text-2xl font-semibold'>Match</h1>
          <p className='text-muted-foreground text-sm'>Incoming requests are assigned to the eligible staff member with the lowest active workload</p>
          <p className='text-muted-foreground mt-1 text-sm'>
            {summary.new_unassigned_count} new or unassigned in your scope
          </p>
        </div>
        <Button type='button' variant='outline' onClick={() => void load()}>
          <RefreshCwIcon />
          Refresh
        </Button>
      </div>

      {summary.unassigned > 0 && (
        <Alert>
          <AlertTitle>{summary.unassigned} unassigned request{summary.unassigned === 1 ? '' : 's'}</AlertTitle>
          <AlertDescription>
            No eligible staff was available, or automatic assignment is disabled. Authorized managers can assign these
            requests manually.
          </AlertDescription>
        </Alert>
      )}

      {error && (
        <Alert variant='destructive'>
          <AlertTitle>{errorStatus === 403 ? 'Permission denied' : 'Unable to load requests'}</AlertTitle>
          <AlertDescription>
            {error}
            <Button variant='outline' className='mt-3' onClick={() => void load()}>
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      )}

      <div className='grid gap-3 sm:grid-cols-2 xl:grid-cols-6'>
        {[
          { label: 'New', value: summary.new },
          { label: 'Unassigned', value: summary.unassigned },
          { label: 'Assigned', value: summary.assigned },
          { label: 'In Progress', value: summary.in_progress },
          { label: 'Urgent', value: summary.urgent },
          { label: 'Resolved', value: summary.resolved }
        ].map(card => (
          <Card key={card.label} className='shadow-none'>
            <CardHeader className='pb-2'>
              <CardDescription>{card.label}</CardDescription>
              <CardTitle className='text-xl'>{card.value}</CardTitle>
            </CardHeader>
          </Card>
        ))}
      </div>

      <div className='grid gap-3 xl:grid-cols-2'>
        <Card className='shadow-none'>
          <CardHeader>
            <CardTitle>Assignment settings</CardTitle>
            <CardDescription>Stored for this account. New requests use lowest active workload.</CardDescription>
          </CardHeader>
          <CardContent className='space-y-4'>
            <label className='flex items-center justify-between gap-3 text-sm'>
              <span>Automatic assignment</span>
              <Switch
                checked={Boolean(settings?.auto_assign_enabled)}
                disabled={!canAssign || savingSettings || !settings}
                onCheckedChange={checked => void saveSetting({ auto_assign_enabled: checked })}
              />
            </label>
            <label className='flex items-center justify-between gap-3 text-sm'>
              <span>Only staff assigned to the request property</span>
              <Switch
                checked={Boolean(settings?.property_staff_only)}
                disabled={!canAssign || savingSettings || !settings}
                onCheckedChange={checked => void saveSetting({ property_staff_only: checked })}
              />
            </label>
            <label className='flex items-center justify-between gap-3 text-sm'>
              <span>Organization-wide staff when no property exists</span>
              <Switch
                checked={Boolean(settings?.org_wide_when_no_property)}
                disabled={!canAssign || savingSettings || !settings}
                onCheckedChange={checked => void saveSetting({ org_wide_when_no_property: checked })}
              />
            </label>
            <p className='text-muted-foreground text-sm'>
              Assignment mode: {settings?.assignment_mode_label || 'Lowest active workload'}
            </p>
          </CardContent>
        </Card>
        <Card className='shadow-none'>
          <CardHeader>
            <CardTitle>Staff workload</CardTitle>
            <CardDescription>Active request counts from the database, not this page.</CardDescription>
          </CardHeader>
          <CardContent className='overflow-x-auto'>
            {workload.length === 0 ? (
              <p className='text-muted-foreground text-sm'>No staff workload is available for this scope.</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Staff</TableHead>
                    <TableHead>Property</TableHead>
                    <TableHead className='text-right'>Active requests</TableHead>
                    <TableHead>Eligible</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {workload.map(row => (
                    <TableRow key={row.id}>
                      <TableCell className='font-medium'>{row.display_name || row.name}</TableCell>
                      <TableCell>
                        {row.assigned_properties.length
                          ? row.assigned_properties.map(item => item.name).join(', ')
                          : '—'}
                      </TableCell>
                      <TableCell className='text-right'>{row.active_requests}</TableCell>
                      <TableCell>{row.eligible ? 'Yes' : 'No'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className='shadow-none'>
        <CardHeader className='gap-4'>
          <div className='flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between'>
            <div>
              <CardTitle>Incoming requests</CardTitle>
              <CardDescription>Assign new work from bookings, quotes, payments, and inquiries.</CardDescription>
            </div>
            <InputGroup className='lg:max-w-80'>
              <InputGroupAddon>
                <SearchIcon className='size-4' />
              </InputGroupAddon>
              <InputGroupInput
                type='search'
                placeholder='Search request, customer, property...'
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
              <SelectItem value='all'>All</SelectItem>
              {meta.statuses.map(item => (
                <SelectItem key={item.id} value={item.id}>
                  {item.label}
                </SelectItem>
              ))}
            </FilterSelect>
            <FilterSelect label='Request type' value={type} onValueChange={value => changeFilter(setType, value)}>
              <SelectItem value='all'>All types</SelectItem>
              {meta.types.map(item => (
                <SelectItem key={item.id} value={item.id}>
                  {item.label}
                </SelectItem>
              ))}
            </FilterSelect>
            <FilterSelect label='Priority' value={priority} onValueChange={value => changeFilter(setPriority, value)}>
              <SelectItem value='all'>All priorities</SelectItem>
              {meta.priorities.map(item => (
                <SelectItem key={item.id} value={item.id}>
                  {item.label}
                </SelectItem>
              ))}
            </FilterSelect>
            <FilterSelect label='Property' value={property} onValueChange={value => changeFilter(setProperty, value)}>
              <SelectItem value='all'>All properties</SelectItem>
              {meta.properties.map((item: PipelineProperty) => (
                <SelectItem key={item.id} value={String(item.id)}>
                  {item.name}
                </SelectItem>
              ))}
            </FilterSelect>
            <FilterSelect label='Assigned staff' value={staff} onValueChange={value => changeFilter(setStaff, value)}>
              <SelectItem value='all'>All staff</SelectItem>
              <SelectItem value='unassigned'>Unassigned</SelectItem>
              {meta.staff.map(user => (
                <SelectItem key={user.id} value={String(user.id)}>
                  {user.display_name || user.name || user.username}
                </SelectItem>
              ))}
            </FilterSelect>
            <FilterSelect label='Unassigned only' value={unassignedOnly} onValueChange={value => changeFilter(setUnassignedOnly, value)}>
              <SelectItem value='0'>All requests</SelectItem>
              <SelectItem value='1'>Unassigned only</SelectItem>
            </FilterSelect>
            <FilterSelect label='Date range' value={due} onValueChange={value => changeFilter(setDue, value)}>
              <SelectItem value='all'>All dates</SelectItem>
              <SelectItem value='today'>Today</SelectItem>
              <SelectItem value='this_week'>This week</SelectItem>
              <SelectItem value='overdue'>Overdue</SelectItem>
              <SelectItem value='custom'>Custom range</SelectItem>
            </FilterSelect>
            <FilterSelect label='Sort' value={ordering} onValueChange={value => changeFilter(setOrdering, value)}>
              <SelectItem value='-created_at'>Created (newest)</SelectItem>
              <SelectItem value='created_at'>Created (oldest)</SelectItem>
              <SelectItem value='due_at'>Due date</SelectItem>
              <SelectItem value='-due_at'>Due date (newest)</SelectItem>
              <SelectItem value='-priority'>Priority</SelectItem>
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
          {loading && <p className='text-muted-foreground text-sm'>Loading requests…</p>}
          {!loading && error && <p className='text-muted-foreground text-sm'>Requests could not be loaded.</p>}
          {!loading && !error && items.length === 0 && (
            <div className='flex flex-col gap-3'>
              <p className='text-muted-foreground text-sm'>
                {filtersActive ? 'No requests match your filters.' : 'No incoming requests.'}
              </p>
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
                  <TableHead>Request</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Subject</TableHead>
                  <TableHead>Customer</TableHead>
                  <TableHead>Property</TableHead>
                  <TableHead>Related</TableHead>
                  <TableHead>Priority</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Assigned</TableHead>
                  <TableHead>Assignment</TableHead>
                  <TableHead>Assigned at</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Due</TableHead>
                  <TableHead className='text-right'>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map(item => {
                  const href = relatedRecordHref(item)

                  return (
                    <TableRow
                      key={item.id}
                      className={cn('cursor-pointer', isHighlightedRequest(item) && 'bg-destructive/5')}
                      onClick={() => void openDetail(item)}
                    >
                      <TableCell className='font-medium'>{item.request_number}</TableCell>
                      <TableCell>{item.request_type_label}</TableCell>
                      <TableCell className='max-w-48 truncate'>{item.subject}</TableCell>
                      <TableCell>{item.customer?.name ?? '—'}</TableCell>
                      <TableCell>{item.property?.name ?? '—'}</TableCell>
                      <TableCell>
                        {item.related_record ? (
                          href ? (
                            <Link href={href} className='hover:underline' onClick={event => event.stopPropagation()}>
                              {item.related_record.label}
                            </Link>
                          ) : (
                            item.related_record.label
                          )
                        ) : (
                          '—'
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant='outline'
                          className={cn(item.priority === 'urgent' && 'border-destructive/40 text-destructive')}
                        >
                          {item.priority_label}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant='outline' className={cn(item.is_overdue && 'text-destructive')}>
                          {item.status_label}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className='flex flex-col gap-1'>
                          <span>{staffLabel(item.assigned_to)}</span>
                          {item.unassigned_reason && !item.assigned_to ? (
                            <span className='text-muted-foreground text-xs'>{item.unassigned_reason}</span>
                          ) : null}
                        </div>
                      </TableCell>
                      <TableCell>
                        {assignmentBadgeLabel(item.assignment_method) ? (
                          <Badge variant='outline'>{assignmentBadgeLabel(item.assignment_method)}</Badge>
                        ) : (
                          '—'
                        )}
                      </TableCell>
                      <TableCell>{formatDueAt(item.assigned_at) || '—'}</TableCell>
                      <TableCell>{formatRelativeTime(item.created_at) || '—'}</TableCell>
                      <TableCell className={cn(item.is_overdue && 'text-destructive')}>{formatDueAt(item.due_at) || '—'}</TableCell>
                      <TableCell className='text-right'>
                        <Button
                          type='button'
                          size='sm'
                          variant='outline'
                          onClick={event => {
                            event.stopPropagation()
                            void openDetail(item)
                          }}
                        >
                          Open
                        </Button>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          )}
          {!loading && !error && items.length > 0 && (
            <div className='mt-4 flex flex-wrap items-center justify-between gap-3 text-sm'>
              <p className='text-muted-foreground'>
                Showing {start}-{end} of {count}
              </p>
              <div className='flex gap-2'>
                <Button type='button' variant='outline' disabled={page <= 1} onClick={() => void setPage(page - 1)}>
                  Previous
                </Button>
                <Button type='button' variant='outline' disabled={!hasNext} onClick={() => void setPage(page + 1)}>
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <MatchDetailSheet
        request={selected}
        statuses={meta.statuses}
        priorities={meta.priorities}
        canAssign={canAssign}
        canReassign={canReassign}
        canUnassign={canUnassign}
        canChangeStatus={canChangeStatus}
        canChangePriority={canChangePriority}
        canAddNotes={canAddNotes}
        canResolve={canResolve}
        assigning={assigning}
        onOpenChange={open => !open && setSelected(null)}
        onCustomer={item => setCustomer(customerFromRequest(item))}
        onAssign={(item, staffId) => void runAction(() => matchApi.assign(item.id, staffId), 'Request assigned.', 'Unable to assign this request.')}
        onReassign={(item, staffId) =>
          void runAction(() => matchApi.reassign(item.id, staffId), 'Request reassigned.', 'Unable to reassign this request.')
        }
        onUnassign={item => void runAction(() => matchApi.unassign(item.id), 'Request unassigned.', 'Unable to unassign this request.')}
        onAutoAssign={item =>
          void runAction(() => matchApi.assignAutomatically(item.id), 'Request assigned automatically.', 'Unable to assign this request automatically.')
        }
        onStatus={(item, nextStatus) =>
          void runAction(() => matchApi.update(item.id, { status: nextStatus }), 'Status updated.', 'Unable to change status.')
        }
        onPriority={(item, nextPriority) =>
          void runAction(() => matchApi.update(item.id, { priority: nextPriority }), 'Priority updated.', 'Unable to change priority.')
        }
        onNote={(item, note) => void runAction(() => matchApi.addNote(item.id, note), 'Note added.', 'Unable to add note.')}
      />

      <CustomerDetailSheet customer={customer} onOpenChange={open => !open && setCustomer(null)} />
    </div>
  )
}

export default MatchPageView
