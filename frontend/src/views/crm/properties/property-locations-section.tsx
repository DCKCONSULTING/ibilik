'use client'

import { useEffect, useMemo, useState, type ReactNode } from 'react'

import Link from 'next/link'
import { PlusIcon, SearchIcon } from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { FieldLabel } from '@/components/ui/field'
import { InputGroup, InputGroupAddon, InputGroupInput } from '@/components/ui/input-group'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { isApiError } from '@/lib/api'
import { locationsApi } from '@/lib/locations/api'
import { occupancyBadgeClass, statusBadgeClass } from '@/lib/locations/badges'
import { LOCATION_OCCUPANCIES, LOCATION_STATUSES, LOCATION_TYPES, type Location, type LocationOption } from '@/lib/locations/types'
import { cn } from '@/lib/utils'
import { formatLocationCapacity, formatLocationRate } from '@/lib/locations/validation'

import LocationDetailSheet from './location-detail-sheet'
import LocationFormDialog from './location-form-dialog'

const FILTER_FIELD_CLASS = 'grid min-w-0 grid-cols-[5.5rem_minmax(0,1fr)] items-center gap-2'

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

type PropertyLocationsSectionProps = {
  propertyId: number
  canEdit: boolean
  onCreated: () => void
}

const PropertyLocationsSection = ({ propertyId, canEdit, onCreated }: PropertyLocationsSectionProps) => {
  const [locations, setLocations] = useState<Location[]>([])
  const [types, setTypes] = useState<LocationOption[]>([...LOCATION_TYPES])
  const [statuses, setStatuses] = useState<LocationOption[]>([...LOCATION_STATUSES])
  const [search, setSearch] = useState('')
  const [type, setType] = useState('all')
  const [status, setStatus] = useState('all')
  const [occupancy, setOccupancy] = useState('all')
  const [active, setActive] = useState('all')
  const [loading, setLoading] = useState(true)
  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState<Location | null>(null)
  const [selected, setSelected] = useState<Location | null>(null)

  useEffect(() => {
    let mounted = true

    const handle = window.setTimeout(() => {
      setLoading(true)
      locationsApi
        .list(propertyId, {
          search: search.trim() || undefined,
          type: type === 'all' ? undefined : type,
          status: status === 'all' ? undefined : status,
          occupancy: occupancy === 'all' ? undefined : occupancy,
          active: active === 'all' ? undefined : active
        })
        .then(payload => {
          if (!mounted) return
          setLocations(payload.results)
          setTypes(payload.types.length > 0 ? payload.types : [...LOCATION_TYPES])
          setStatuses(payload.statuses.length > 0 ? payload.statuses : [...LOCATION_STATUSES])
        })
        .catch(error => {
          if (!mounted) return
          toast.error(isApiError(error) ? error.message : 'Unable to load locations.')
        })
        .finally(() => {
          if (!mounted) return
          setLoading(false)
        })
    }, 250)

    return () => {
      mounted = false
      window.clearTimeout(handle)
    }
  }, [active, occupancy, propertyId, search, status, type])

  const refreshSelected = (location: Location) => {
    setLocations(current => current.map(item => (item.id === location.id ? { ...item, ...location } : item)))
    setSelected(current => (current?.id === location.id ? { ...current, ...location } : current))
  }

  const openCreate = () => {
    setEditing(null)
    setFormOpen(true)
  }

  const openEdit = (location: Location) => {
    setEditing(location)
    setFormOpen(true)
  }

  const handleSaved = (location: Location) => {
    const existed = locations.some(item => item.id === location.id)

    setLocations(current => {
      if (current.some(item => item.id === location.id)) {
        return current.map(item => (item.id === location.id ? { ...item, ...location } : item))
      }

      return [...current, location].sort((left, right) => left.name.localeCompare(right.name))
    })
    setSelected(current => (current?.id === location.id ? { ...current, ...location } : current))
    if (!existed) onCreated()
  }

  const deactivate = async (location: Location) => {
    try {
      const next = await locationsApi.deactivate(location.id)

      refreshSelected(next)
      toast.success('Location deactivated.')
    } catch (error) {
      toast.error(isApiError(error) ? error.message : 'Unable to deactivate the location.')
    }
  }

  const openDetail = async (location: Location) => {
    setSelected(location)

    try {
      const detail = await locationsApi.get(location.id)

      setSelected(detail)
      setLocations(current => current.map(item => (item.id === detail.id ? { ...item, ...detail } : item)))
    } catch (error) {
      toast.error(isApiError(error) ? error.message : 'Unable to load location details.')
    }
  }

  const typeOptions = useMemo(() => [{ id: 'all', label: 'All' }, ...types], [types])
  const statusOptions = useMemo(() => [{ id: 'all', label: 'All' }, ...statuses], [statuses])

  return (
    <section className='space-y-3'>
      <div className='flex items-center justify-between gap-3'>
        <h3 className='font-medium'>Locations</h3>
        {canEdit && (
          <Button size='sm' onClick={openCreate}>
            <PlusIcon />
            Add Location
          </Button>
        )}
      </div>
      <div className='grid gap-3 sm:grid-cols-2'>
        <InputGroup>
          <InputGroupAddon>
            <SearchIcon />
          </InputGroupAddon>
          <InputGroupInput
            placeholder='Search name or code'
            value={search}
            onChange={event => setSearch(event.target.value)}
          />
        </InputGroup>
        <FilterSelect label='Type' value={type} onValueChange={value => setType(value ?? 'all')}>
          {typeOptions.map(item => (
            <SelectItem key={item.id} value={item.id}>
              {item.label}
            </SelectItem>
          ))}
        </FilterSelect>
        <FilterSelect label='Occupancy' value={occupancy} onValueChange={value => setOccupancy(value ?? 'all')}>
          <SelectItem value='all'>All</SelectItem>
          {LOCATION_OCCUPANCIES.map(item => (
            <SelectItem key={item.id} value={item.id}>
              {item.label}
            </SelectItem>
          ))}
        </FilterSelect>
        <FilterSelect label='Status' value={status} onValueChange={value => setStatus(value ?? 'all')}>
          {statusOptions.map(item => (
            <SelectItem key={item.id} value={item.id}>
              {item.label}
            </SelectItem>
          ))}
        </FilterSelect>
        <FilterSelect label='Active' value={active} onValueChange={value => setActive(value ?? 'all')}>
          <SelectItem value='all'>All</SelectItem>
          <SelectItem value='true'>Active</SelectItem>
          <SelectItem value='false'>Inactive</SelectItem>
        </FilterSelect>
      </div>
      {loading ? (
        <p className='text-muted-foreground text-sm'>Loading locations…</p>
      ) : locations.length === 0 ? (
        <p className='text-muted-foreground text-sm'>No locations match the current filters.</p>
      ) : (
        <ul className='space-y-2'>
          {locations.map(item => (
            <li key={item.id}>
              <div className='flex items-center gap-2 rounded-md border px-3 py-2'>
                <Link href={`/properties/${propertyId}/locations/${item.id}`} className='min-w-0 flex-1 hover:underline'>
                  <p className='truncate text-sm font-medium'>{item.name}</p>
                  <p className='text-muted-foreground truncate text-xs'>
                    {[
                      item.type_label,
                      item.code,
                      item.floor ? `Floor ${item.floor}` : null,
                      item.capacity ? `Cap ${formatLocationCapacity(item.capacity)}` : null,
                      formatLocationRate(item.base_rate, item.currency),
                      item.current_booking?.customer.name || item.upcoming_booking?.customer.name
                    ]
                      .filter(value => value && value !== '—')
                      .join(' · ')}
                  </p>
                </Link>
                <Badge variant='outline' className={cn(occupancyBadgeClass(item.occupancy))}>
                  {item.occupancy_label || item.occupancy || '—'}
                </Badge>
                <Badge variant='outline' className={cn(statusBadgeClass(item.status))}>
                  {item.status_label}
                </Badge>
                <Button type='button' size='sm' variant='ghost' onClick={() => void openDetail(item)}>
                  Quick view
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <LocationFormDialog
        open={formOpen}
        propertyId={propertyId}
        location={editing}
        types={types}
        statuses={statuses}
        onOpenChange={setFormOpen}
        onSaved={handleSaved}
      />
      <LocationDetailSheet
        location={selected}
        canEdit={canEdit}
        onOpenChange={open => {
          if (!open) setSelected(null)
        }}
        onEdit={location => {
          setSelected(null)
          openEdit(location)
        }}
        onDeactivate={location => void deactivate(location)}
      />
    </section>
  )
}

export default PropertyLocationsSection
