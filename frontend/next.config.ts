import os from 'node:os'
import path from 'node:path'

import type { NextConfig } from 'next'

const djangoOrigin = (process.env.DJANGO_ORIGIN ?? 'http://127.0.0.1:8000').replace(/\/$/, '')

const resolveDistDir = () => {
  if (process.env.NEXT_DIST_DIR) {
    return process.env.NEXT_DIST_DIR
  }

  const isDev = process.argv.includes('dev')

  if (process.platform === 'win32' && isDev) {
    const localAppData = process.env.LOCALAPPDATA ?? path.join(os.homedir(), 'AppData', 'Local')

    return path.join(localAppData, 'hotel-crm-frontend', 'next')
  }

  return '.next'
}

const nextConfig: NextConfig = {
  basePath: process.env.BASEPATH ?? '',
  distDir: resolveDistDir(),
  reactStrictMode: true,
  skipTrailingSlashRedirect: true,
  pageExtensions: ['js', 'jsx', 'ts', 'tsx'],
  redirects: async () => {
    return [
      {
        source: '/apps/users',
        destination: '/apps/users/list',
        permanent: true
      }
    ]
  },
  rewrites: async () => {
    const djangoApiPrefixes = [
      'auth',
      'users',
      'roles',
      'permissions',
      'dashboard',
      'customers',
      'conversations',
      'inbox',
      'integrations',
      'cases',
      'follow-ups',
      'opportunities',
      'pipeline',
      'properties',
      'locations',
      'availability',
      'quotes',
      'bookings',
      'payments',
      'refunds',
      'match',
      'calendar',
      'reports',
      'settings'
    ]

    return djangoApiPrefixes.flatMap(prefix => [
      {
        source: `/api/${prefix}`,
        destination: `${djangoOrigin}/api/${prefix}/`
      },
      {
        source: `/api/${prefix}/`,
        destination: `${djangoOrigin}/api/${prefix}/`
      },
      {
        source: `/api/${prefix}/:path*`,
        destination: `${djangoOrigin}/api/${prefix}/:path*/`
      }
    ])
  }
}

export default nextConfig
