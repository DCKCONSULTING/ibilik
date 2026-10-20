'use client'

import type { ReactNode } from 'react'

import { useAuth } from '@/components/auth/auth-provider'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

export const RequirePermission = ({
  permission,
  children
}: {
  permission: string | string[]
  children: ReactNode
}) => {
  const { can, loading } = useAuth()

  if (loading) {
    return <p className='text-muted-foreground text-sm'>Checking permissions…</p>
  }

  if (!can(permission)) {
    return (
      <Alert variant='destructive'>
        <AlertTitle>Access denied</AlertTitle>
        <AlertDescription>You do not have permission to perform this action.</AlertDescription>
      </Alert>
    )
  }

  return children
}
