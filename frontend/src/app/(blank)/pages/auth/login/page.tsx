import type { Metadata } from 'next'

import Login from '@/views/pages/auth/login'

export const metadata: Metadata = {
  title: 'Sign in'
}

const LoginPage = () => {
  return <Login />
}

export default LoginPage
