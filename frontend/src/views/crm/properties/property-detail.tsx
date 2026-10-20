'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'

import Link from 'next/link'
import { useParams } from 'next/navigation'
import { parseAsString, useQueryState } from 'nuqs'

import { useAuth } from '@/components/auth/auth-provider'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { isApiError } from '@/lib/api'
import { propertiesApi } from '@/lib/properties/api'
import type { Property } from '@/lib/properties/types'
import { formatPropertyAddress, formatPropertyRate } from '@/lib/properties/validation'

import AddPropertyDialog from './add-property-dialog'
import ExcelImportDialog from './excel-import-dialog'
import PropertyExcelMenu from './property-excel-menu'
import PropertyGeneralSection from './property-general-section'
import PropertyLocationsSection from './property-locations-section'
import {
  PropertyAvailabilitySection,
  PropertyBookingsSection,
  PropertyCasesSection,
  PropertyPaymentsSection,
  PropertyQuotesSection
} from './property-related-tables'
import PropertyStaffSection from './property-staff-section'

const ALL_TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'general', label: 'General' },
  { id: 'locations', label: 'Locations' },
  { id: 'staff', label: 'Staff' },
  { id: 'availability', label: 'Availability' },
  { id: 'bookings', label: 'Bookings' },
  { id: 'quotes', label: 'Quotes' },
  { id: 'cases', label: 'Cases' },
  { id: 'payments', label: 'Payments' }
] as const

const SummaryCard = ({ label, value }: { label: string; value: number }) => (
  <Card className='shadow-none'>
    <CardContent className='px-4 py-4'>
      <p className='text-muted-foreground text-xs'>{label}</p>
      <p className='text-2xl font-semibold'>{value}</p>
    </CardContent>
  </Card>
)

const PropertyDetailView = () => {
  const params = useParams<{ id: string }>()
  const propertyId = Number(params.id)
  const validId = Number.isInteger(propertyId) && propertyId > 0
  const { can } = useAuth()
  const canEdit = can('properties.change_property')
  const canManageStaff = can('properties.manage_staff')
  const canViewUsers = can('users.view_user')

  const visibleTabs = useMemo(() => {
    return ALL_TABS.filter(tab => {
      if (tab.id === 'availability') return can('availability.view_availability')
      if (tab.id === 'bookings') return can(['bookings.view_booking', 'cases.view_case', 'opportunities.view_opportunity'])
      if (tab.id === 'quotes') return can('quotes.view_quote')
      if (tab.id === 'cases') return can(['cases.view_case', 'opportunities.view_opportunity'])
      if (tab.id === 'payments') return can('payments.view_payment')

      return true
    })
  }, [can])

  const [tab, setTab] = useQueryState(
    'tab',
    parseAsString.withDefault('overview').withOptions({ history: 'replace', shallow: true, clearOnDefault: true })
  )

  const [property, setProperty] = useState<Property | null>(null)
  const [loading, setLoading] = useState(validId)
  const [error, setError] = useState<string | null>(validId ? null : 'Property not found.')
  const [errorStatus, setErrorStatus] = useState<number | null>(validId ? null : 404)
  const [editOpen, setEditOpen] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const activeTab = visibleTabs.some(item => item.id === tab) ? tab : 'overview'

  const loadProperty = useCallback(() => {
    return propertiesApi.get(propertyId).then(payload => {
      setProperty(payload)
      setError(null)
      setErrorStatus(null)

      return payload
    })
  }, [propertyId])

  useEffect(() => {
    if (!validId) return

    let mounted = true

    loadProperty()
      .catch(err => {
        if (!mounted) return
        setProperty(null)
        setErrorStatus(isApiError(err) ? err.status : null)

        if (isApiError(err) && err.status === 403) {
          setError('You do not have access to this property.')
        } else if (isApiError(err) && err.status === 404) {
          setError('Property not found.')
        } else {
          setError(isApiError(err) ? err.message : 'Unable to load property.')
        }
      })
      .finally(() => {
        if (!mounted) return
        setLoading(false)
      })

    return () => {
      mounted = false
    }
  }, [loadProperty, validId])

  const retry = () => {
    setLoading(true)
    void loadProperty()
      .catch(err => {
        setProperty(null)
        setErrorStatus(isApiError(err) ? err.status : null)
        setError(isApiError(err) ? err.message : 'Unable to load property.')
      })
      .finally(() => setLoading(false))
  }

  if (loading) {
    return <p className='text-muted-foreground text-sm'>Loading property…</p>
  }

  if (error || !property) {
    return (
      <div className='flex flex-col gap-4'>
        <Button render={<Link href='/properties' />} nativeButton={false} variant='ghost' className='w-fit px-0'>
          ← Back to Properties
        </Button>
        <Alert variant='destructive'>
          <AlertTitle>{errorStatus === 404 ? 'Property not found.' : errorStatus === 403 ? 'Not authorized' : 'Unable to load property.'}</AlertTitle>
          <AlertDescription className='flex flex-col gap-3'>
            <span>{error ?? 'Please try again.'}</span>
            <div className='flex flex-wrap gap-2'>
              <Button type='button' variant='outline' className='w-fit' onClick={retry}>
                Try Again
              </Button>
              <Button render={<Link href='/properties' />} nativeButton={false} variant='outline' className='w-fit'>
                Back to Properties
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      </div>
    )
  }

  const summary = property.summary

  const handleUpdated = (next: Property) => {
    setProperty(current => ({ ...current, ...next, summary: next.summary ?? current?.summary, staff: next.staff ?? current?.staff }))
  }

  return (
    <div className='flex flex-col gap-6'>
      <div>
        <Button render={<Link href='/properties' />} nativeButton={false} variant='ghost' className='mb-2 w-fit px-0'>
          ← Back to Properties
        </Button>
        <p className='text-muted-foreground mb-2 text-sm'>
          <Link href='/properties' className='hover:text-foreground'>
            Properties
          </Link>
          {' / '}
          {property.name}
        </p>
        <div className='flex flex-wrap items-start justify-between gap-3'>
          <div>
            <h1 className='text-2xl font-semibold'>{property.name}</h1>
            <p className='text-muted-foreground text-sm'>
              {[property.property_type_label, property.city, property.region, property.country].filter(Boolean).join(' • ')}
            </p>
          </div>
          <div className='flex flex-wrap gap-2'>
            <PropertyExcelMenu canImport={canEdit} propertyId={property.id} onImport={() => setImportOpen(true)} />
            {canEdit && <Button onClick={() => setEditOpen(true)}>Edit Property</Button>}
          </div>
        </div>
      </div>

      {summary && (
        <div className='text-muted-foreground flex flex-wrap gap-x-6 gap-y-1 text-sm'>
          <span>{summary.location_count} Locations</span>
          <span>{summary.booking_count} Bookings</span>
          <span>{summary.case_count} Cases</span>
          <span>{summary.quote_count} Quotes</span>
        </div>
      )}

      <Tabs
        value={activeTab}
        onValueChange={value => {
          if (value) void setTab(value)
        }}
      >
        <div className='overflow-x-auto sm:overflow-visible'>
          <TabsList
            variant='line'
            className='h-fit! w-max min-w-full flex-nowrap justify-start gap-0 rounded-none border-b p-0 sm:w-full'
          >
            {visibleTabs.map(item => (
              <TabsTrigger
                key={item.id}
                value={item.id}
                className='not-data-active:hover:group-data-horizontal/tabs:after:bg-muted-foreground/30 shrink-0 border-0 group-data-horizontal/tabs:after:bottom-[-0.5px] not-data-active:hover:group-data-horizontal/tabs:after:opacity-100'
              >
                {item.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </div>

        <TabsContent value='overview' className='space-y-6 pt-6'>
          {summary && (
            <div className='grid gap-3 sm:grid-cols-2 lg:grid-cols-3'>
              <SummaryCard label='Locations' value={summary.location_count} />
              <SummaryCard label='Available' value={summary.available_count} />
              <SummaryCard label='In house' value={summary.occupied_count} />
              <SummaryCard label='Upcoming Bookings' value={summary.upcoming_bookings_count} />
              <SummaryCard label='Open Cases' value={summary.open_cases_count} />
              <SummaryCard label='Pending Quotes' value={summary.pending_quotes_count} />
            </div>
          )}
          <dl className='grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4'>
            <div>
              <dt className='text-muted-foreground'>Hotel name</dt>
              <dd className='font-medium'>{property.name}</dd>
            </div>
            <div>
              <dt className='text-muted-foreground'>Property type</dt>
              <dd className='font-medium'>{property.property_type_label || property.property_type}</dd>
            </div>
            <div className='sm:col-span-2'>
              <dt className='text-muted-foreground'>Address</dt>
              <dd className='font-medium'>{formatPropertyAddress(property) || '—'}</dd>
            </div>
            <div>
              <dt className='text-muted-foreground'>City / region</dt>
              <dd className='font-medium'>{[property.city, property.region].filter(Boolean).join(', ') || '—'}</dd>
            </div>
            <div>
              <dt className='text-muted-foreground'>Country</dt>
              <dd className='font-medium'>{property.country || '—'}</dd>
            </div>
            <div>
              <dt className='text-muted-foreground'>Phone</dt>
              <dd className='font-medium'>{property.phone || '—'}</dd>
            </div>
            <div>
              <dt className='text-muted-foreground'>Email</dt>
              <dd className='font-medium'>{property.email || '—'}</dd>
            </div>
            <div>
              <dt className='text-muted-foreground'>Website</dt>
              <dd className='font-medium'>{property.website || '—'}</dd>
            </div>
            <div>
              <dt className='text-muted-foreground'>Currency</dt>
              <dd className='font-medium'>{property.currency || '—'}</dd>
            </div>
            <div>
              <dt className='text-muted-foreground'>Base rate</dt>
              <dd className='font-medium'>{formatPropertyRate(property.rate, property.currency)}</dd>
            </div>
            <div>
              <dt className='text-muted-foreground'>Check-in / check-out</dt>
              <dd className='font-medium'>
                {property.check_in_time || '—'} / {property.check_out_time || '—'}
              </dd>
            </div>
            <div>
              <dt className='text-muted-foreground'>Timezone</dt>
              <dd className='font-medium'>{property.timezone || '—'}</dd>
            </div>
            <div className='sm:col-span-2 lg:col-span-4'>
              <dt className='text-muted-foreground'>Description</dt>
              <dd className='font-medium'>{property.description || '—'}</dd>
            </div>
            <div className='sm:col-span-2 lg:col-span-4'>
              <dt className='text-muted-foreground'>Staff assignments</dt>
              <dd className='font-medium'>
                {property.staff && property.staff.length > 0
                  ? property.staff.map(member => member.display_name || member.username).join(', ')
                  : 'No staff assigned'}
              </dd>
            </div>
          </dl>
        </TabsContent>

        <TabsContent value='general' className='pt-6'>
          <PropertyGeneralSection property={property} canEdit={canEdit} onUpdated={handleUpdated} />
        </TabsContent>

        <TabsContent value='locations' className='pt-6'>
          {activeTab === 'locations' && (
            <PropertyLocationsSection
              propertyId={property.id}
              canEdit={canEdit}
              onCreated={() => {
                void loadProperty()
              }}
            />
          )}
        </TabsContent>

        <TabsContent value='staff' className='pt-6'>
          {activeTab === 'staff' && (
            <PropertyStaffSection
              property={property}
              canManage={canManageStaff}
              canViewUsers={canViewUsers}
              onUpdated={handleUpdated}
            />
          )}
        </TabsContent>

        <TabsContent value='availability' className='pt-6'>
          {activeTab === 'availability' && <PropertyAvailabilitySection propertyId={property.id} />}
        </TabsContent>

        <TabsContent value='bookings' className='pt-6'>
          {activeTab === 'bookings' && <PropertyBookingsSection propertyId={property.id} />}
        </TabsContent>

        <TabsContent value='quotes' className='pt-6'>
          {activeTab === 'quotes' && <PropertyQuotesSection propertyId={property.id} />}
        </TabsContent>

        <TabsContent value='cases' className='pt-6'>
          {activeTab === 'cases' && <PropertyCasesSection propertyId={property.id} />}
        </TabsContent>

        <TabsContent value='payments' className='pt-6'>
          {activeTab === 'payments' && <PropertyPaymentsSection propertyId={property.id} />}
        </TabsContent>
      </Tabs>

      <AddPropertyDialog open={editOpen} property={property} onOpenChange={setEditOpen} onSaved={handleUpdated} />
      <ExcelImportDialog
        open={importOpen}
        onOpenChange={setImportOpen}
        propertyId={property.id}
        defaultMode='locations'
        onImported={() => {
          void loadProperty()
        }}
      />
    </div>
  )
}

export default PropertyDetailView
