import type { Metadata } from 'next'

import { RequirePermission } from '@/components/auth/require-permission'
import PropertyDetailView from '@/views/crm/properties/property-detail'

export const metadata: Metadata = {
  title: 'Property'
}

const PropertyDetailPage = () => {
  return (
    <RequirePermission permission='properties.view_property'>
      <PropertyDetailView />
    </RequirePermission>
  )
}

export default PropertyDetailPage
