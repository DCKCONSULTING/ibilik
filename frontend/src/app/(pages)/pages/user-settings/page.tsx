import type { Metadata } from 'next'

// Component Imports
import UserSetting from '@/views/pages/user-settings'

export const metadata: Metadata = {
  title: 'Settings'
}

const UserSettingsPage = async () => {
  return <UserSetting />
}

export default UserSettingsPage
