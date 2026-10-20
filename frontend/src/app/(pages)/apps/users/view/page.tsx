import type { Metadata } from 'next'

// Component Imports
import UserViewApp from '@/views/apps/users/view'

export const metadata: Metadata = {
  title: 'User'
}

const UserViewPage = () => {
  return <UserViewApp />
}

export default UserViewPage
