// Next Imports
import Link from 'next/link'

// Config Imports
import { brand } from '@/configs/brand'

// Component Import
import Logo from '@/components/shared/Logo'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import RegisterForm from '@/views/pages/auth/register/register-form'

const Register = () => {
  return (
    <div className='relative flex h-auto min-h-dvh items-center justify-center overflow-x-hidden px-4 py-10 sm:px-6 lg:px-8'>
      <Card className='z-1 w-full gap-6 py-6 sm:max-w-lg'>
        <CardHeader className='gap-6 px-6'>
          <Link href='/' aria-label={brand.productName}>
            <Logo className='gap-3' />
          </Link>

          <div>
            <CardTitle className='mb-2 text-2xl font-semibold'>Request {brand.productName} access</CardTitle>
            <CardDescription className='text-base'>Create a staff account for {brand.productName}.</CardDescription>
          </div>
        </CardHeader>

        <CardContent className='px-6'>
          <div className='space-y-4'>
            <RegisterForm />

            <p className='text-muted-foreground text-center'>
              Already have an account?{' '}
              <Link href='/pages/auth/login' className='text-card-foreground hover:underline'>
                Sign in instead
              </Link>
            </p>

            <p className='text-muted-foreground text-center text-sm'>Access is limited to {brand.name} staff.</p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default Register
