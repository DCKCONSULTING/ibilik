// This file is used to fetch the nav-apps from the JSON and validate them. It should be removed when the nav-apps API is removed.

// Next Imports
import { NextResponse } from 'next/server'

// Util Imports
import { api } from '@/lib/api'
import { env } from '@/lib/env'

export async function GET() {
  try {
    const payload = await api.get<unknown>(env.navAppsUrl, { cache: 'no-store' })

    if (!Array.isArray(payload)) {
      return NextResponse.json([], { status: 502 })
    }

    return NextResponse.json(payload)
  } catch {
    return NextResponse.json([], { status: 502 })
  }
}
