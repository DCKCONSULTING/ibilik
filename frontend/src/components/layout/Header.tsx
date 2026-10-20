'use client'

// Next Imports
import { Fragment } from 'react'

import { usePathname } from 'next/navigation'

// Third-party Imports
import { LanguagesIcon } from 'lucide-react'

// Config Imports
import { brand } from '@/configs/brand'

// Component Imports
import LanguageDropdown from '@/components/shared/LanguageDropdown'
import ModeToggle from '@/components/layout/ModeToggle'
import PropertySwitcher from '@/components/properties/property-switcher'
import ProfileDropdown from '@/components/shared/ProfileDropdown'
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator
} from '@/components/ui/breadcrumb'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { SidebarTrigger } from '@/components/ui/sidebar'

const Header = () => {
  const pathname = usePathname()

  const segments = pathname.split('/').filter(Boolean)

  return (
    <header className='bg-card sticky top-0 z-50 border-b'>
      <div className='flex w-full items-center justify-between gap-4 px-4 py-2'>
        <div className='flex min-w-0 items-center gap-4'>
          <SidebarTrigger className='[&_svg]:size-5!' />
          <Separator orientation='vertical' className='hidden h-4! data-vertical:self-center sm:block' />
          <p className='truncate text-sm font-semibold sm:hidden'>{brand.productName}</p>
          <Breadcrumb className='hidden sm:block'>
            <BreadcrumbList>
              {segments.map((segment, index) => {
                const isLast = index === segments.length - 1
                const label = segment.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
                const href = '/' + segments.slice(0, index + 1).join('/')

                return (
                  <Fragment key={href}>
                    <BreadcrumbItem>
                      {isLast ? <BreadcrumbPage>{label}</BreadcrumbPage> : <BreadcrumbLink>{label}</BreadcrumbLink>}
                    </BreadcrumbItem>
                    {!isLast && <BreadcrumbSeparator />}
                  </Fragment>
                )
              })}
            </BreadcrumbList>
          </Breadcrumb>
        </div>
        <div className='flex items-center gap-1.5'>
          <PropertySwitcher />
          <ModeToggle />
          <LanguageDropdown
            trigger={
              <Button variant='ghost' size='icon-lg' aria-label='Change language'>
                <LanguagesIcon />
              </Button>
            }
          />
          <ProfileDropdown />
        </div>
      </div>
    </header>
  )
}

export default Header
