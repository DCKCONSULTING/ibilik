'use client'

import { ChevronDownIcon } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { isApiError } from '@/lib/api'
import { propertiesApi } from '@/lib/properties/api'

type PropertyExcelMenuProps = {
  canImport: boolean
  propertyId?: number
  onImport: () => void
}

const run = async (action: () => Promise<unknown>, fallback: string) => {
  try {
    await action()
  } catch (error) {
    toast.error(isApiError(error) ? error.message : fallback)
  }
}

const PropertyExcelMenu = ({ canImport, propertyId, onImport }: PropertyExcelMenuProps) => {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger render={<Button variant='outline' />}>
        Excel
        <ChevronDownIcon />
      </DropdownMenuTrigger>
      <DropdownMenuContent align='end' className='min-w-56'>
        {propertyId ? (
          <>
            <DropdownMenuItem onClick={() => void run(() => propertiesApi.exportPortfolio(propertyId), 'Unable to export this property.')}>
              Export Property Excel
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => void run(() => propertiesApi.exportLocations(propertyId), 'Unable to export locations.')}>
              Export Locations Excel
            </DropdownMenuItem>
          </>
        ) : (
          <>
            <DropdownMenuItem onClick={() => void run(() => propertiesApi.exportProperties(), 'Unable to export properties.')}>
              Export Properties Excel
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => void run(() => propertiesApi.exportLocations(), 'Unable to export locations.')}>
              Export Locations Excel
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => void run(() => propertiesApi.exportPortfolio(), 'Unable to export the portfolio.')}>
              Export Portfolio Excel
            </DropdownMenuItem>
          </>
        )}
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => void run(() => propertiesApi.downloadImportTemplate(), 'Unable to download the template.')}>
          Download Import Template
        </DropdownMenuItem>
        {canImport && (
          <DropdownMenuItem onClick={onImport}>{propertyId ? 'Import Locations Excel' : 'Import Excel'}</DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export default PropertyExcelMenu
