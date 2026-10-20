'use client'

import { useEffect, useMemo, useState } from 'react'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { isApiError } from '@/lib/api'
import { authApi } from '@/lib/auth/api'
import type { PermissionDefinition } from '@/lib/auth/types'

const PermissionCatalog = () => {
  const [permissions, setPermissions] = useState<PermissionDefinition[]>([])
  const [sectionNames, setSectionNames] = useState<Record<string, string>>({})
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    authApi
      .listPermissions()
      .then(payload => {
        setPermissions(payload.results)
        setSectionNames(Object.fromEntries((payload.sections ?? []).map(section => [section.id, section.name])))
      })
      .catch(err => setError(isApiError(err) ? err.message : 'Unable to load permissions.'))
  }, [])

  const grouped = useMemo(() => {
    return permissions.reduce<Record<string, PermissionDefinition[]>>((acc, permission) => {
      const key = permission.section || permission.module
      acc[key] = acc[key] ?? []
      acc[key].push(permission)

      return acc
    }, {})
  }, [permissions])

  return (
    <div className='flex flex-col gap-6'>
      <div>
        <h1 className='text-2xl font-semibold'>Permissions</h1>
        <p className='text-muted-foreground text-sm'>
          Permission definitions and grouping. Assign these permissions to roles, not to individual users.
        </p>
      </div>

      {error && (
        <Alert variant='destructive'>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className='grid gap-4 md:grid-cols-2'>
        {Object.entries(grouped).map(([module, items]) => (
          <Card key={module} className='shadow-none'>
            <CardHeader>
              <CardTitle className='capitalize'>{sectionNames[module] || module}</CardTitle>
              <CardDescription>Application permissions for this module.</CardDescription>
            </CardHeader>
            <CardContent className='space-y-2 text-sm'>
              {items.map(item => (
                <div key={item.codename}>
                  <div className='font-medium'>{item.name}</div>
                  <div className='text-muted-foreground text-xs'>{item.codename}</div>
                </div>
              ))}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

export default PermissionCatalog
