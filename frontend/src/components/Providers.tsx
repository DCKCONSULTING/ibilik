// React Imports
import type { ReactNode } from 'react'

// Component Imports
import { AuthProvider } from '@/components/auth/auth-provider'
import { RequireAuth } from '@/components/auth/require-auth'
import { PropertyProvider } from '@/components/properties/property-provider'

import { ThemeProvider } from './ThemeProvider'
import { SidebarProvider } from './ui/sidebar'
import { TooltipProvider } from './ui/tooltip'

type Props = {
  children: ReactNode
  sidebarDefaultOpen?: boolean
}

const Providers = ({ children, sidebarDefaultOpen }: Props) => {
  return (
    <ThemeProvider attribute='class' defaultTheme='system' enableSystem={true}>
      <TooltipProvider>
        <AuthProvider>
          <RequireAuth>
            <PropertyProvider>
              <SidebarProvider defaultOpen={sidebarDefaultOpen}>{children}</SidebarProvider>
            </PropertyProvider>
          </RequireAuth>
        </AuthProvider>
      </TooltipProvider>
    </ThemeProvider>
  )
}

export default Providers
