import type { Metadata } from 'next'

import { RequirePermission } from '@/components/auth/require-permission'
import PropertiesPageView from '@/views/crm/properties'

export const metadata: Metadata = {
  title: 'Properties'
}

const PropertiesPage = () => {
  return (
    <RequirePermission permission='properties.view_property'>
      <PropertiesPageView />
    </RequirePermission>
  )
}

export default PropertiesPage
