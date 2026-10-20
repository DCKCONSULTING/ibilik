'use client'

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import { useAuth } from '@/components/auth/auth-provider'
import { defaultPropertyContext, hasGlobalPropertyAccess } from '@/lib/auth/permissions'
import { propertiesApi } from '@/lib/properties/api'
import type { Property } from '@/lib/properties/types'

const STORAGE_KEY = 'ibilik.currentPropertyId'

type CurrentPropertyId = number | 'all' | null

type PropertyContextValue = {
  properties: Property[]
  currentPropertyId: CurrentPropertyId
  setCurrentPropertyId: (id: number | 'all') => void
  hasGlobalAccess: boolean
  loading: boolean
  refresh: () => Promise<void>
}

const PropertyContext = createContext<PropertyContextValue | null>(null)

const readStoredId = (): CurrentPropertyId => {
  if (typeof window === 'undefined') return null

  const stored = window.sessionStorage.getItem(STORAGE_KEY)

  if (!stored) return null
  if (stored === 'all') return 'all'

  const numeric = Number(stored)

  return Number.isInteger(numeric) ? numeric : null
}

const persistId = (id: CurrentPropertyId) => {
  if (typeof window === 'undefined') return

  if (id === null) {
    window.sessionStorage.removeItem(STORAGE_KEY)

    return
  }

  window.sessionStorage.setItem(STORAGE_KEY, String(id))
}

export const PropertyProvider = ({ children }: { children: ReactNode }) => {
  const { user, can } = useAuth()
  const [properties, setProperties] = useState<Property[]>([])
  const [currentPropertyId, setCurrentPropertyIdState] = useState<CurrentPropertyId>(null)
  const [loading, setLoading] = useState(false)
  const canViewProperties = can('properties.view_property')
  const globalAccess = hasGlobalPropertyAccess(user)
  const userId = user?.id ?? null

  const applyDefault = useCallback(
    (items: Property[]) => {
      const accessibleIds = items.map(item => item.id)
      const stored = readStoredId()

      const storedIsValid =
        stored === 'all' ? globalAccess : typeof stored === 'number' && accessibleIds.includes(stored)

      const next = storedIsValid ? stored : defaultPropertyContext(user, accessibleIds)

      setCurrentPropertyIdState(next)
      persistId(next)
    },
    [globalAccess, user]
  )

  const refresh = useCallback(async () => {
    if (!user || !canViewProperties) {
      setProperties([])
      setCurrentPropertyIdState(null)

      return
    }

    try {
      const payload = await propertiesApi.list()

      setProperties(payload.results)
      applyDefault(payload.results)
    } catch {
      setProperties([])
    }
  }, [applyDefault, canViewProperties, user])

  useEffect(() => {
    let mounted = true

    if (!userId || !canViewProperties) {
      return () => {
        mounted = false
      }
    }

    propertiesApi
      .list()
      .then(payload => {
        if (!mounted) return
        setProperties(payload.results)
        applyDefault(payload.results)
      })
      .catch(() => {
        if (!mounted) return
        setProperties([])
      })
      .finally(() => {
        if (!mounted) return
        setLoading(false)
      })

    return () => {
      mounted = false
    }
  }, [applyDefault, canViewProperties, userId])

  const setCurrentPropertyId = useCallback(
    (id: number | 'all') => {
      if (id === 'all') {
        if (!globalAccess) return
        setCurrentPropertyIdState('all')
        persistId('all')

        return
      }

      if (!properties.some(item => item.id === id)) return

      setCurrentPropertyIdState(id)
      persistId(id)
    },
    [globalAccess, properties]
  )

  const value = useMemo(
    () => ({
      properties,
      currentPropertyId,
      setCurrentPropertyId,
      hasGlobalAccess: globalAccess,
      loading,
      refresh
    }),
    [currentPropertyId, globalAccess, loading, properties, refresh, setCurrentPropertyId]
  )

  return <PropertyContext.Provider value={value}>{children}</PropertyContext.Provider>
}

export const usePropertyContext = () => {
  const context = useContext(PropertyContext)

  if (!context) {
    throw new Error('usePropertyContext must be used within PropertyProvider')
  }

  return context
}

export const useListPropertyQuery = (pageProperty: string) => {
  const { currentPropertyId } = usePropertyContext()

  if (pageProperty !== 'all') return pageProperty
  if (typeof currentPropertyId === 'number') return String(currentPropertyId)

  return undefined
}
