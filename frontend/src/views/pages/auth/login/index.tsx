// Next Imports
import Link from 'next/link'

// Config Imports
import { brand } from '@/configs/brand'

// Components Import
import Logo from '@/components/shared/Logo'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import LoginForm from '@/views/pages/auth/login/login-form'

const Login = () => {
  return (
    <div className='relative flex h-auto min-h-dvh items-center justify-center overflow-x-hidden px-4 py-10 sm:px-6 lg:px-8'>
      <Card className='z-1 w-full gap-6 py-6 sm:max-w-lg'>
        <CardHeader className='gap-6 px-6'>
          <Link href='/' aria-label={brand.productName}>
            <Logo className='gap-3' />
          </Link>

          <div>
            <CardTitle className='mb-2 text-2xl font-semibold'>{brand.productName}</CardTitle>
            <CardDescription className='text-base'>Sign in to your account</CardDescription>
          </div>
        </CardHeader>

        <CardContent className='px-6'>
          <div className='space-y-4'>
            <LoginForm />

            <p className='text-muted-foreground text-center text-base'>
              Access is granted by an administrator. Contact your iBilik manager if you need an account.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default Login
