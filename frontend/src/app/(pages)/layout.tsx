// React Imports
import type { ReactNode } from 'react'

// Component Imports
import AppLayout from '@/components/layout/AppLayout'

const PagesLayout = ({ children }: Readonly<{ children: ReactNode }>) => {
  return <AppLayout>{children}</AppLayout>
}

export default PagesLayout
