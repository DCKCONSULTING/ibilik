'use client'

// Next Imports
import Link from 'next/link'

// Third-party Imports
import { Building2Icon, CalendarCheckIcon, LanguagesIcon, UsersIcon } from 'lucide-react'

// Config Imports
import { brand } from '@/configs/brand'

// Component Imports
import LanguageDropdown from '@/components/shared/LanguageDropdown'
import Logo from '@/components/shared/Logo'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import LoginForm from '@/views/pages/auth/login/login-form'

const capabilities = [
  { icon: UsersIcon, label: 'Customers & enquiries' },
  { icon: Building2Icon, label: 'Properties & quotations' },
  { icon: CalendarCheckIcon, label: 'Bookings & revenue' }
] as const

const HomePage = () => {
  return (
    <div className='bg-background flex min-h-dvh flex-col overflow-x-hidden'>
      <header className='border-border/80 bg-background/90 sticky top-0 z-40 border-b backdrop-blur-sm'>
        <div className='mx-auto flex w-full max-w-6xl items-center justify-between gap-3 px-4 py-3 sm:px-6'>
          <Link href='/' aria-label={brand.productName}>
            <Logo />
          </Link>
          <div className='flex items-center gap-1'>
            <Popover>
              <PopoverTrigger
                render={
                  <Button variant='ghost' aria-label='Help'>
                    Help
                  </Button>
                }
              />
              <PopoverContent align='end' className='w-72'>
                <p className='font-medium'>{brand.productName} access</p>
                <p className='text-muted-foreground mt-2 text-sm'>
                  This is an internal staff system. If you need an account, contact your iBilik administrator.
                </p>
              </PopoverContent>
            </Popover>
            <LanguageDropdown
              trigger={
                <Button variant='ghost' size='icon-lg' aria-label='Change language'>
                  <LanguagesIcon />
                </Button>
              }
            />
          </div>
        </div>
      </header>

      <main className='mx-auto flex w-full max-w-6xl flex-1 flex-col justify-center px-4 py-8 sm:px-6 lg:py-16'>
        <div className='grid items-center gap-10 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,24rem)] lg:gap-16'>
          <section className='min-w-0 space-y-6 text-center lg:text-left'>
            <p className='text-muted-foreground text-sm font-medium tracking-[0.18em] uppercase'>{brand.name}</p>
            <div className='space-y-3'>
              <h1 className='text-4xl font-semibold tracking-tight text-balance sm:text-5xl'>{brand.productName}</h1>
              <p className='text-lg text-pretty sm:text-xl'>{brand.tagline}</p>
            </div>
            <p className='text-muted-foreground mx-auto max-w-xl text-base text-pretty lg:mx-0'>{brand.summary}</p>
            <ul className='mx-auto flex max-w-xl flex-col gap-3 sm:flex-row sm:flex-wrap sm:justify-center lg:mx-0 lg:justify-start'>
              {capabilities.map(item => {
                const Icon = item.icon

                return (
                  <li
                    key={item.label}
                    className='bg-card text-card-foreground flex items-center justify-center gap-2 rounded-lg border px-3 py-2 text-sm sm:justify-start'
                  >
                    <Icon className='size-4 shrink-0' aria-hidden='true' />
                    <span>{item.label}</span>
                  </li>
                )
              })}
            </ul>
          </section>

          <Card className='w-full gap-6 py-6'>
            <CardHeader className='gap-2 px-6'>
              <CardTitle className='text-2xl font-semibold'>{brand.productName}</CardTitle>
              <CardDescription className='text-base'>Sign in to your account</CardDescription>
            </CardHeader>
            <CardContent className='px-6'>
              <LoginForm />
            </CardContent>
          </Card>
        </div>
      </main>

      <footer className='border-border/80 border-t'>
        <div className='text-muted-foreground mx-auto flex w-full max-w-6xl flex-col items-center justify-between gap-2 px-4 py-4 text-center text-sm sm:flex-row sm:px-6 sm:text-left'>
          <p>{brand.accessNote}</p>
          <p>
            {brand.productName} · ©{new Date().getFullYear()} {brand.name}
          </p>
        </div>
      </footer>
    </div>
  )
}

export default HomePage
