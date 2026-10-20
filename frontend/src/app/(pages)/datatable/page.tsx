import type { Metadata } from 'next'

// Component Imports
import DataTable from '@/views/datatables'

export const metadata: Metadata = {
  title: 'Data Table'
}

const DataTablePage = () => {
  return <DataTable />
}

export default DataTablePage
