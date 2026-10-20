'use client'

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import { usePathname, useRouter } from 'next/navigation'

import { isApiError } from '@/lib/api'
import { authApi } from '@/lib/auth/api'
import { canAccess } from '@/lib/auth/permissions'
import type { AuthUser } from '@/lib/auth/types'
import themeConfig from '@/configs/themeConfig'

type AuthContextValue = {
  user: AuthUser | null
  loading: boolean
  login: (username: string, password: string) => Promise<AuthUser>
  logout: () => Promise<void>
  refresh: () => Promise<AuthUser | null>
  can: (permission?: string | string[]) => boolean
}

const AuthContext = createContext<AuthContextValue | null>(null)

const PUBLIC_PREFIXES = ['/pages/auth']

const isPublicPath = (pathname: string) => pathname === '/' || PUBLIC_PREFIXES.some(prefix => pathname.startsWith(prefix))

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const pathname = usePathname()
  const router = useRouter()
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const current = await authApi.me()

      setUser(current)

      return current
    } catch (error) {
      setUser(null)

      if (isApiError(error) && error.status === 401 && !isPublicPath(pathname)) {
        router.replace('/')
      }

      return null
    } finally {
      setLoading(false)
    }
  }, [pathname, router])

  useEffect(() => {
    let mounted = true

    authApi
      .me()
      .then(current => {
        if (!mounted) return
        setUser(current)
      })
      .catch(() => {
        if (!mounted) return
        setUser(null)
      })
      .finally(() => {
        if (!mounted) return
        setLoading(false)
      })

    return () => {
      mounted = false
    }
  }, [])

  const login = useCallback(
    async (username: string, password: string) => {
      await authApi.csrf()
      const response = await authApi.login(username, password)

      setUser(response.user)
      router.replace(themeConfig.homePageUrl)
      router.refresh()

      return response.user
    },
    [router]
  )

  const logout = useCallback(async () => {
    try {
      await authApi.logout()
    } finally {
      setUser(null)
      router.replace('/')
      router.refresh()
    }
  }, [router])

  const can = useCallback((permission?: string | string[]) => canAccess(user, permission), [user])

  const value = useMemo(
    () => ({
      user,
      loading,
      login,
      logout,
      refresh,
      can
    }),
    [user, loading, login, logout, refresh, can]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => {
  const context = useContext(AuthContext)

  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }

  return context
}
