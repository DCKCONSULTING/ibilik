'use client'

import { useAuth } from '@/components/auth/auth-provider'
import { usePropertyContext } from '@/components/properties/property-provider'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

const ALL_VALUE = 'all'

const uniqueNamedProperties = (
  items: Array<{ id: number; name: string }>
): Array<{ id: number; name: string }> => {
  const seen = new Set<number>()

  return items.filter(item => {
    if (!item.name || seen.has(item.id)) return false
    seen.add(item.id)

    return true
  })
}

const PropertySwitcher = () => {
  const { user, can } = useAuth()
  const { properties, currentPropertyId, setCurrentPropertyId, hasGlobalAccess, loading } = usePropertyContext()
  const sessionProperties = uniqueNamedProperties([
    ...(user?.assigned_properties ?? []),
    ...(user?.visible_properties ?? [])
  ])
  const namedProperties = properties.length > 0 ? properties : sessionProperties

  if (!can('properties.view_property')) return null
  if (!hasGlobalAccess && namedProperties.length === 0) return null

  const value = currentPropertyId === null ? null : String(currentPropertyId)
  const items: Record<string, string> = Object.fromEntries(namedProperties.map(property => [String(property.id), property.name]))

  if (hasGlobalAccess) {
    items[ALL_VALUE] = 'All Properties'
  }

  const selectedLabel = value == null ? undefined : items[value]
  const triggerLabel = value == null ? undefined : selectedLabel ?? (loading ? 'Loading…' : 'Select property')

  return (
    <div className='flex min-w-0 items-center gap-2'>
      <span className='text-muted-foreground hidden text-xs font-medium sm:inline'>Property</span>
      <Select
        items={items}
        value={value}
        onValueChange={next => {
          if (!next) return

          if (next === ALL_VALUE) {
            setCurrentPropertyId('all')

            return
          }

          setCurrentPropertyId(Number(next))
        }}
      >
        <SelectTrigger size='sm' className='max-w-52' disabled={loading} aria-label='Current property'>
          <SelectValue placeholder={loading ? 'Loading…' : 'Select property'}>{triggerLabel}</SelectValue>
        </SelectTrigger>
        <SelectContent>
          {hasGlobalAccess && <SelectItem value={ALL_VALUE}>{items[ALL_VALUE]}</SelectItem>}
          {namedProperties.map(property => (
            <SelectItem key={property.id} value={String(property.id)}>
              {property.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

export default PropertySwitcher
