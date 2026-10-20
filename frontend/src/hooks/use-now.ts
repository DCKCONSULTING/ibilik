'use client'

import { useEffect, useState } from 'react'

export const useNow = (intervalMs = 60_000) => {
  const [now, setNow] = useState(() => new Date())

  useEffect(() => {
    const handle = window.setInterval(() => setNow(new Date()), intervalMs)

    return () => window.clearInterval(handle)
  }, [intervalMs])

  return now
}
