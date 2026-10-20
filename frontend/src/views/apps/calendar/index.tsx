'use client'

import { useEffect, useMemo, useState, type ReactNode } from 'react'

import {
  addDays,
  addMonths,
  addWeeks,
  endOfMonth,
  endOfWeek,
  format,
  isSameMonth,
  startOfDay,
  startOfMonth,
  startOfWeek,
  subMonths,
  subWeeks
} from 'date-fns'
import { CalendarCheckIcon, ChevronDownIcon, ChevronLeftIcon, ChevronRightIcon, SearchIcon } from 'lucide-react'
import { parseAsString, useQueryState } from 'nuqs'
import { toast } from 'sonner'

import { EventGap, EventHeight, WeekCellsHeight } from '@/assets/data/constants'
import { useAuth } from '@/components/auth/auth-provider'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuShortcut,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { FieldLabel } from '@/components/ui/field'
import { InputGroup, InputGroupAddon, InputGroupInput } from '@/components/ui/input-group'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { isApiError } from '@/lib/api'
import { calendarApi } from '@/lib/calendar/api'
import type { CalendarApiEvent, CalendarEventsResponse } from '@/lib/calendar/types'
import { followUpsApi } from '@/lib/pipeline/api'
import type { CaseFollowUp, PipelineProperty, PipelineUser } from '@/lib/pipeline/types'
import type { CalendarEvent, CalendarView } from '@/types/apps/calendar-types'
import { cn } from '@/lib/utils'
import CaseFollowUpDialog from '@/views/crm/pipeline/case-follow-up-dialog'

import CalendarEventSheet from './calendar-event-sheet'
import { DayView } from './day-view'
import { MonthView } from './month-view'
import { WeekView } from './week-view'

export interface EventCalendarProps {
  className?: string
  initialView?: CalendarView
}

const queryOptions = { history: 'replace' as const, clearOnDefault: true }
const FILTER_FIELD_CLASS = 'grid min-w-0 grid-cols-[8rem_minmax(0,1fr)] items-center gap-2'

const STATUS_OPTIONS = [
  { id: 'all', label: 'All' },
  { id: 'pending', label: 'Pending' },
  { id: 'completed', label: 'Completed' },
  { id: 'cancelled', label: 'Cancelled' },
  { id: 'overdue', label: 'Overdue' },
  { id: 'expected', label: 'Expected' },
  { id: 'received', label: 'Received' }
]

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

const toCalendarEvent = (item: CalendarApiEvent): CalendarEvent => ({
  id: item.id,
  title: item.title,
  description: String(item.metadata.follow_up_title || item.metadata.amount_label || item.customer.name),
  start: new Date(item.start),
  end: new Date(item.end),
  allDay: item.all_day,
  color: item.type as CalendarEvent['color'],
  location: item.property?.name,
  source: item
})

const followUpFromEvent = (event: CalendarApiEvent): CaseFollowUp => ({
  id: event.source_id,
  case_id: event.case.id,
  type: String(event.metadata.follow_up_type || 'follow_up'),
  type_label: event.type_label,
  title: String(event.metadata.follow_up_title || event.title),
  description: String(event.metadata.description || ''),
  status: event.status || 'pending',
  status_label: event.status_label || 'Pending',
  assigned_to: event.staff,
  due_at: event.start,
  completed_at: null,
  created_at: null,
  updated_at: null,
  case: event.case,
  customer: event.customer,
  property: event.property
})

export function EventCalendar({ className, initialView = 'month' }: EventCalendarProps) {
  const { can } = useAuth()
  const canChangeFollowUp = can(['opportunities.change_opportunity', 'cases.change_case'])
  const canViewUsers = can('users.view_user')
  const [currentDate, setCurrentDate] = useState(() => new Date())
  const [view, setView] = useState<CalendarView>(initialView)
  const [type, setType] = useQueryState('type', parseAsString.withDefault('all').withOptions(queryOptions))
  const [property, setProperty] = useQueryState('property', parseAsString.withDefault('all').withOptions(queryOptions))
  const [staff, setStaff] = useQueryState('staff', parseAsString.withDefault('all').withOptions(queryOptions))
  const [stage, setStage] = useQueryState('stage', parseAsString.withDefault('all').withOptions(queryOptions))
  const [source, setSource] = useQueryState('source', parseAsString.withDefault('all').withOptions(queryOptions))
  const [status, setStatus] = useQueryState('status', parseAsString.withDefault('all').withOptions(queryOptions))
  const [search, setSearch] = useQueryState('search', parseAsString.withDefault('').withOptions(queryOptions))
  const [items, setItems] = useState<CalendarEvent[]>([])

  const [meta, setMeta] = useState<Pick<CalendarEventsResponse, 'types' | 'stages' | 'sources' | 'staff' | 'properties'>>({
    types: [],
    stages: [],
    sources: [],
    staff: [],
    properties: []
  })

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [errorStatus, setErrorStatus] = useState<number | null>(null)
  const [selected, setSelected] = useState<CalendarApiEvent | null>(null)
  const [editorOpen, setEditorOpen] = useState(false)
  const [editing, setEditing] = useState<CaseFollowUp | null>(null)

  const visibleRange = useMemo(() => {
    if (view === 'month') {
      const monthStart = startOfMonth(currentDate)
      const monthEnd = endOfMonth(monthStart)

      return {
        start: startOfWeek(monthStart, { weekStartsOn: 0 }),
        end: addDays(endOfWeek(monthEnd, { weekStartsOn: 0 }), 1)
      }
    }

    if (view === 'week') {
      const start = startOfWeek(currentDate, { weekStartsOn: 0 })

      return { start, end: addDays(endOfWeek(currentDate, { weekStartsOn: 0 }), 1) }
    }

    const start = startOfDay(currentDate)

    return { start, end: addDays(start, 1) }
  }, [currentDate, view])

  const filtersActive = useMemo(
    () =>
      type !== 'all' ||
      property !== 'all' ||
      staff !== 'all' ||
      stage !== 'all' ||
      source !== 'all' ||
      status !== 'all' ||
      Boolean(search.trim()),
    [property, search, source, staff, stage, status, type]
  )

  const load = () => {
    setLoading(true)

    return calendarApi
      .getEvents({
        start: visibleRange.start.toISOString(),
        end: visibleRange.end.toISOString(),
        type: type !== 'all' ? type : undefined,
        property: property !== 'all' ? property : undefined,
        staff: staff !== 'all' ? staff : undefined,
        case_stage: stage !== 'all' ? stage : undefined,
        source: source !== 'all' ? source : undefined,
        status: status !== 'all' ? status : undefined,
        search: search.trim() || undefined
      })
      .then(payload => {
        setItems(payload.results.map(toCalendarEvent))
        setMeta({
          types: payload.types,
          stages: payload.stages,
          sources: payload.sources,
          staff: payload.staff,
          properties: payload.properties
        })
        setError(null)
        setErrorStatus(null)
      })
      .catch(err => {
        setItems([])
        setError(isApiError(err) ? err.message : 'Unable to load calendar events.')
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
  }, [visibleRange.start, visibleRange.end, type, property, staff, stage, source, status, search])

  const clearFilters = () => {
    void setType('all')
    void setProperty('all')
    void setStaff('all')
    void setStage('all')
    void setSource('all')
    void setStatus('all')
    void setSearch('')
  }

  const changeFilter = (setter: (value: string) => unknown, value: string | null) => {
    if (!value) return
    void setter(value)
  }

  const goToToday = () => setCurrentDate(new Date())

  const goToPrevious = () => {
    setCurrentDate(current => {
      if (view === 'month') return subMonths(current, 1)
      if (view === 'week') return subWeeks(current, 1)

      return addDays(current, -1)
    })
  }

  const goToNext = () => {
    setCurrentDate(current => {
      if (view === 'month') return addMonths(current, 1)
      if (view === 'week') return addWeeks(current, 1)

      return addDays(current, 1)
    })
  }

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        (e.target instanceof HTMLElement && e.target.isContentEditable)
      ) {
        return
      }

      switch (e.key.toLowerCase()) {
        case 'm':
          setView('month')
          break
        case 'w':
          setView('week')
          break
        case 'd':
          setView('day')
          break
      }
    }

    window.addEventListener('keydown', handleKeyDown)

    return () => {
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [])

  const viewTitle = useMemo(() => {
    if (view === 'month') {
      return format(currentDate, 'MMMM yyyy')
    } else if (view === 'week') {
      const start = startOfWeek(currentDate, { weekStartsOn: 0 })
      const end = endOfWeek(currentDate, { weekStartsOn: 0 })

      if (isSameMonth(start, end)) {
        return format(start, 'MMMM yyyy')
      } else {
        return `${format(start, 'MMM')} - ${format(end, 'MMM yyyy')}`
      }
    } else if (view === 'day') {
      return (
        <>
          <span className='min-[480px]:hidden' aria-hidden='true'>
            {format(currentDate, 'MMM d, yyyy')}
          </span>
          <span className='max-[479px]:hidden md:hidden' aria-hidden='true'>
            {format(currentDate, 'MMMM d, yyyy')}
          </span>
          <span className='max-md:hidden'>{format(currentDate, 'EEE MMMM d, yyyy')}</span>
        </>
      )
    } else {
      return format(currentDate, 'MMMM yyyy')
    }
  }, [currentDate, view])

  const completeFollowUp = async (event: CalendarApiEvent) => {
    try {
      await followUpsApi.complete(event.source_id)
      toast.success('Follow-up completed.')
      setSelected(null)
      await load()
    } catch (err) {
      toast.error(isApiError(err) ? err.message : 'Unable to complete this follow-up.')
    }
  }

  return (
    <div className='flex flex-col gap-4'>
      {error && (
        <Alert variant='destructive'>
          <AlertTitle>{errorStatus === 403 ? 'Permission denied' : 'API error'}</AlertTitle>
          <AlertDescription className='flex flex-wrap items-center justify-between gap-3'>
            <span>{error}</span>
            <Button type='button' size='sm' variant='outline' onClick={() => void load()}>
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      )}
      {!loading && !error && items.length === 0 && (
        <div className='flex flex-wrap items-center justify-between gap-3'>
          <p className='text-muted-foreground text-sm'>No events found</p>
          {filtersActive && (
            <Button type='button' variant='outline' size='sm' onClick={clearFilters}>
              Clear filters
            </Button>
          )}
        </div>
      )}
      <div className='bg-card flex flex-col rounded-lg border'>
        <div
          className='flex flex-col has-data-[slot=month-view]:flex-1'
          style={
            {
              '--event-height': `${EventHeight}px`,
              '--event-gap': `${EventGap}px`,
              '--week-cells-height': `${WeekCellsHeight}px`
            } as React.CSSProperties
          }
        >
          <div className={cn('flex items-center justify-between gap-1 p-2 sm:p-4', className)}>
            <div className='flex items-center gap-1 max-sm:justify-between sm:gap-4'>
              <div className='flex items-center gap-1'>
                <Button variant='outline' className='max-sm:hidden md:max-lg:h-8' onClick={goToToday}>
                  <CalendarCheckIcon size={16} aria-hidden='true' />
                  <span>Today</span>
                </Button>
                <Button variant='outline' size='icon-sm' className='sm:hidden' onClick={goToToday}>
                  <CalendarCheckIcon size={16} aria-hidden='true' />
                </Button>
              </div>
            </div>
            <div className='flex items-center gap-1'>
              <Button variant='ghost' size='icon-sm' onClick={goToPrevious} aria-label='Previous'>
                <ChevronLeftIcon size={16} aria-hidden='true' />
              </Button>
              <h2 className='text-sm font-semibold sm:text-lg md:text-xl'>{viewTitle}</h2>
              <Button variant='ghost' size='icon-sm' onClick={goToNext} aria-label='Next'>
                <ChevronRightIcon size={16} aria-hidden='true' />
              </Button>
            </div>
            <div className='flex items-center gap-2'>
              <DropdownMenu>
                <DropdownMenuTrigger render={<Button variant='outline' className='max-sm:h-8!' />}>
                  <span>
                    <span className='sm:hidden' aria-hidden='true'>
                      {view.charAt(0).toUpperCase()}
                    </span>
                    <span className='max-sm:sr-only'>{view.charAt(0).toUpperCase() + view.slice(1)}</span>
                  </span>
                  <ChevronDownIcon className='-me-1 opacity-60' size={16} aria-hidden='true' />
                </DropdownMenuTrigger>
                <DropdownMenuContent align='end' className='min-w-32'>
                  <DropdownMenuItem onClick={() => setView('month')}>
                    Month <DropdownMenuShortcut>M</DropdownMenuShortcut>
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => setView('week')}>
                    Week <DropdownMenuShortcut>W</DropdownMenuShortcut>
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => setView('day')}>
                    Day <DropdownMenuShortcut>D</DropdownMenuShortcut>
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>

          <div className='flex flex-col gap-3 border-t px-2 py-3 sm:px-4'>
            <div className='flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between'>
              <p className='text-muted-foreground text-sm'>
                {loading ? 'Loading events…' : `${items.length} event${items.length === 1 ? '' : 's'} in this view.`}
              </p>
              <InputGroup className='lg:max-w-80'>
                <InputGroupAddon>
                  <SearchIcon className='size-4' />
                </InputGroupAddon>
                <InputGroupInput
                  type='search'
                  placeholder='Search customer, case, property...'
                  value={search}
                  onChange={event => void setSearch(event.target.value)}
                />
              </InputGroup>
            </div>
            <div className='grid gap-3 sm:grid-cols-2 xl:grid-cols-3'>
              <FilterSelect label='Event Type' value={type} onValueChange={value => changeFilter(setType, value)}>
                <SelectItem value='all'>All</SelectItem>
                {meta.types.map(item => (
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
              <FilterSelect label='Source' value={source} onValueChange={value => changeFilter(setSource, value)}>
                <SelectItem value='all'>All Sources</SelectItem>
                {meta.sources.map(item => (
                  <SelectItem key={item.id} value={item.id}>
                    {item.label}
                  </SelectItem>
                ))}
              </FilterSelect>
              <FilterSelect label='Status' value={status} onValueChange={value => changeFilter(setStatus, value)}>
                {STATUS_OPTIONS.map(item => (
                  <SelectItem key={item.id} value={item.id}>
                    {item.label}
                  </SelectItem>
                ))}
              </FilterSelect>
            </div>
            {filtersActive && (
              <Button type='button' variant='outline' className='w-fit' onClick={clearFilters}>
                Clear filters
              </Button>
            )}
          </div>

          <div className='flex flex-1 flex-col'>
            {view === 'month' && (
              <MonthView
                currentDate={currentDate}
                events={items}
                onEventSelect={event => setSelected(event.source ?? null)}
                onEventCreate={() => {}}
              />
            )}
            {view === 'week' && (
              <WeekView
                currentDate={currentDate}
                events={items}
                onEventSelect={event => setSelected(event.source ?? null)}
                onEventCreate={() => {}}
              />
            )}
            {view === 'day' && (
              <DayView
                currentDate={currentDate}
                events={items}
                onEventSelect={event => setSelected(event.source ?? null)}
                onEventCreate={() => {}}
              />
            )}
          </div>
        </div>
      </div>
      <CalendarEventSheet
        event={selected}
        canChangeFollowUp={canChangeFollowUp}
        onOpenChange={open => {
          if (!open) setSelected(null)
        }}
        onCompleteFollowUp={event => void completeFollowUp(event)}
        onEditFollowUp={event => {
          setSelected(null)
          setEditing(followUpFromEvent(event))
          setEditorOpen(true)
        }}
      />
      <CaseFollowUpDialog
        key={editorOpen ? `${editing?.id ?? 'new'}` : 'closed'}
        open={editorOpen}
        followUp={editing}
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
