import type { Metadata } from 'next'

import { RequirePermission } from '@/components/auth/require-permission'
import UserManagement from '@/views/apps/access/user-management'

export const metadata: Metadata = {
  title: 'Users'
}

const UsersPage = () => {
  return (
    <RequirePermission permission='users.view_user'>
      <UserManagement />
    </RequirePermission>
  )
}

export default UsersPage
