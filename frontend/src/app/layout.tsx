// React Imports
import type { ReactNode } from 'react'

// Next Imports
import type { Metadata } from 'next'
import { Geist, Geist_Mono } from 'next/font/google'

// Third-party Imports
import { NuqsAdapter } from 'nuqs/adapters/next/app'

// Component Imports
import Providers from '@/components/Providers'
import { TooltipProvider } from '@/components/ui/tooltip'

// Config Imports
import { brand } from '@/configs/brand'

// Util Imports
import { env } from '@/lib/env'
import { cn } from '@/lib/utils'

// Style Imports
import './globals.css'
import ScrollToTop from '@/components/layout/ScrollToTop'

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin']
})

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin']
})

export const metadata: Metadata = {
  title: {
    default: brand.productName,
    template: `${brand.productName} — %s`
  },
  description: brand.description,
  applicationName: brand.productName,
  metadataBase: new URL(env.appUrl),
  openGraph: {
    title: brand.productName,
    description: brand.description,
    type: 'website',
    siteName: brand.productName,
    url: env.appUrl
  },
  twitter: {
    card: 'summary',
    title: brand.productName,
    description: brand.description
  }
}

const RootLayout = ({ children }: Readonly<{ children: ReactNode }>) => {
  return (
    <html
      lang='en'
      className={cn(geistSans.variable, geistMono.variable, 'flex min-h-full w-full antialiased')}
      data-scroll-behavior='smooth'
      suppressHydrationWarning
    >
      <body className='flex min-h-full w-full flex-auto flex-col' suppressHydrationWarning>
        <NuqsAdapter>
          <Providers sidebarDefaultOpen={true}>
            <TooltipProvider>{children}</TooltipProvider>
          </Providers>
        </NuqsAdapter>

        <ScrollToTop />
      </body>
    </html>
  )
}

export default RootLayout
