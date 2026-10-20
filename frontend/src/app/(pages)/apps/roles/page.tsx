import type { Metadata } from 'next'

import { RequirePermission } from '@/components/auth/require-permission'
import RoleManagement from '@/views/apps/access/role-management'

export const metadata: Metadata = {
  title: 'Roles'
}

const RolesPage = () => {
  return (
    <RequirePermission permission={['users.view_user', 'users.manage_roles']}>
      <RoleManagement />
    </RequirePermission>
  )
}

export default RolesPage
