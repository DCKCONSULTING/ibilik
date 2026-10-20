import type { Metadata } from 'next'

// Component Imports
import UserProfile from '@/views/pages/user-profile'

export const metadata: Metadata = {
  title: 'Profile'
}

const UserProfilePage = async () => {
  return <UserProfile />
}

export default UserProfilePage
