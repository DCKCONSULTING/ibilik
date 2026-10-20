'use client'

import { useEffect, useState } from 'react'

import { useRouter } from 'next/navigation'
import { PlusIcon } from 'lucide-react'

import { useAuth } from '@/components/auth/auth-provider'
import { usePropertyContext } from '@/components/properties/property-provider'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { isApiError } from '@/lib/api'
import { propertiesApi } from '@/lib/properties/api'
import type { Property } from '@/lib/properties/types'
import { formatPropertyRate } from '@/lib/properties/validation'

import AddPropertyDialog from './add-property-dialog'
import ExcelImportDialog from './excel-import-dialog'
import PropertyExcelMenu from './property-excel-menu'

const PropertiesPageView = () => {
  const router = useRouter()
  const { can } = useAuth()
  const { refresh: refreshPropertyContext } = usePropertyContext()
  const [properties, setProperties] = useState<Property[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [addOpen, setAddOpen] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const canAdd = can('properties.add_property')
  const canImport = can(['properties.add_property', 'properties.change_property'])

  useEffect(() => {
    let mounted = true

    propertiesApi
      .list()
      .then(payload => {
        if (!mounted) return
        setProperties(payload.results)
        setError(null)
      })
      .catch(err => {
        if (!mounted) return
        setError(isApiError(err) ? err.message : 'Unable to load properties.')
      })
      .finally(() => {
        if (!mounted) return
        setLoading(false)
      })

    return () => {
      mounted = false
    }
  }, [])

  const handleCreated = async (property: Property) => {
    setProperties(current => {
      if (current.some(item => item.id === property.id)) {
        return current.map(item => (item.id === property.id ? property : item))
      }

      return [...current, property].sort((left, right) => left.name.localeCompare(right.name))
    })
    await refreshPropertyContext()
  }

  return (
    <div className='flex flex-col gap-6'>
      <div className='flex flex-wrap items-center justify-between gap-3'>
        <div>
          <h1 className='text-2xl font-semibold'>Properties</h1>
          <p className='text-muted-foreground text-sm'>
            Browse hotels you can access. The Django API filters this list for your account.
          </p>
        </div>
        <div className='flex flex-wrap gap-2'>
          <PropertyExcelMenu canImport={canImport} onImport={() => setImportOpen(true)} />
          {canAdd && (
            <Button onClick={() => setAddOpen(true)}>
              <PlusIcon />
              Add Property
            </Button>
          )}
        </div>
      </div>

      {error && (
        <Alert variant='destructive'>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Card className='shadow-none'>
        <CardHeader>
          <CardTitle>Properties</CardTitle>
          <CardDescription>Hotel name, city, type, rate, inventory, staff, and status for each accessible property.</CardDescription>
        </CardHeader>
        <CardContent className='overflow-x-auto'>
          {loading ? (
            <p className='text-muted-foreground text-sm'>Loading properties…</p>
          ) : properties.length === 0 ? (
            <p className='text-muted-foreground text-sm'>No properties are available to your account.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Hotel</TableHead>
                  <TableHead>City / region</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Rate</TableHead>
                  <TableHead className='text-right'>Locations</TableHead>
                  <TableHead className='text-right'>Staff</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {properties.map(property => (
                  <TableRow
                    key={property.id}
                    className='cursor-pointer'
                    onClick={() => router.push(`/properties/${property.id}`)}
                  >
                    <TableCell className='font-medium'>{property.name}</TableCell>
                    <TableCell>
                      {[property.city, property.region].filter(Boolean).join(', ')}
                    </TableCell>
                    <TableCell>{property.property_type_label || property.property_type}</TableCell>
                    <TableCell>{formatPropertyRate(property.rate, property.currency)}</TableCell>
                    <TableCell className='text-right'>
                      {property.location_count === 1 ? '1 Location' : `${property.location_count ?? 0} Locations`}
                    </TableCell>
                    <TableCell className='text-right'>{property.staff_count}</TableCell>
                    <TableCell>
                      <Badge variant={property.status === 'active' ? 'secondary' : 'outline'}>
                        {property.status_label || property.status}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <AddPropertyDialog open={addOpen} onOpenChange={setAddOpen} onSaved={property => void handleCreated(property)} />
      <ExcelImportDialog
        open={importOpen}
        onOpenChange={setImportOpen}
        onImported={() => {
          void propertiesApi.list().then(payload => setProperties(payload.results))
          void refreshPropertyContext()
        }}
      />
    </div>
  )
}

export default PropertiesPageView
