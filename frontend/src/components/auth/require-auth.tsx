'use client'

import { useEffect } from 'react'
import type { ReactNode } from 'react'

import { usePathname, useRouter } from 'next/navigation'

import { useAuth } from '@/components/auth/auth-provider'
import themeConfig from '@/configs/themeConfig'

const PUBLIC_PREFIXES = ['/pages/auth']

const isPublicPath = (pathname: string) => pathname === '/' || PUBLIC_PREFIXES.some(prefix => pathname.startsWith(prefix))

export const RequireAuth = ({ children }: { children: ReactNode }) => {
  const { user, loading } = useAuth()
  const pathname = usePathname()
  const router = useRouter()

  useEffect(() => {
    if (loading) return

    if (!user && !isPublicPath(pathname)) {
      router.replace('/')

      return
    }

    if (user && pathname === '/') {
      router.replace(themeConfig.homePageUrl)
    }
  }, [loading, pathname, router, user])

  if (loading) {
    return (
      <div className='text-muted-foreground flex min-h-dvh items-center justify-center text-sm'>
        Checking your session…
      </div>
    )
  }

  if (!user && !isPublicPath(pathname)) {
    return null
  }

  if (user && pathname === '/') {
    return null
  }

  return children
}
