import type { Metadata } from 'next'

import { RequirePermission } from '@/components/auth/require-permission'
import PermissionCatalog from '@/views/apps/access/permission-catalog'

export const metadata: Metadata = {
  title: 'Permissions'
}

const PermissionsPage = () => {
  return (
    <RequirePermission permission='users.manage_permissions'>
      <PermissionCatalog />
    </RequirePermission>
  )
}

export default PermissionsPage
