const PRODUCTION_APP_URL = 'https://ibilik.dckwebgen.com'
const PRODUCTION_API_URL = 'https://ibilik.dckwebgen.com/api'
const DEFAULT_APP_URL = 'http://localhost:3000'
const DEFAULT_NAV_APPS_URL = 'https://cdn.shadcnstudio.com/ss-assets/template/admincn/nav-apps.json'

const trimTrailingSlash = (value: string) => value.replace(/\/$/, '')

const resolveApiBaseUrl = (value: string) => {
  const trimmed = trimTrailingSlash(value)

  // API helpers already use paths like `/api/auth/login/`.
  // If NEXT_PUBLIC_API_URL is the API root (`.../api`), strip it to avoid `/api/api/...`.
  if (trimmed.endsWith('/api')) {
    return trimTrailingSlash(trimmed.slice(0, -4))
  }

  return trimmed
}

const defaultAppUrl = process.env.NODE_ENV === 'production' ? PRODUCTION_APP_URL : DEFAULT_APP_URL
const defaultApiUrl = process.env.NODE_ENV === 'production' ? PRODUCTION_API_URL : ''

export const env = {
  appUrl: trimTrailingSlash(process.env.NEXT_PUBLIC_APP_URL ?? defaultAppUrl),
  apiBaseUrl: resolveApiBaseUrl(process.env.NEXT_PUBLIC_API_URL || defaultApiUrl),
  navAppsUrl: process.env.NAV_APPS_URL ?? DEFAULT_NAV_APPS_URL
} as const
