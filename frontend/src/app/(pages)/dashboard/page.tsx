import type { Metadata } from 'next'

import DashboardPageView from '@/views/crm/dashboard'

export const metadata: Metadata = {
  title: 'Dashboard'
}

const DashboardPage = () => {
  return <DashboardPageView />
}

export default DashboardPage
