import { Suspense } from 'react'

import type { Metadata } from 'next'

import MailApp from '@/views/apps/mail'

export const metadata: Metadata = {
  title: 'Inbox'
}

const MailPage = () => {
  return (
    <Suspense fallback={<p className='text-muted-foreground text-sm'>Loading inbox…</p>}>
      <MailApp />
    </Suspense>
  )
}

export default MailPage
