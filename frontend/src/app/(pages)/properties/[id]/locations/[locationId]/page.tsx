import type { Metadata } from 'next'

import { RequirePermission } from '@/components/auth/require-permission'
import LocationDetailView from '@/views/crm/properties/location-detail'

export const metadata: Metadata = {
  title: 'Location'
}

const LocationDetailPage = () => {
  return (
    <RequirePermission permission={['locations.view_location', 'properties.view_property']}>
      <LocationDetailView />
    </RequirePermission>
  )
}

export default LocationDetailPage
