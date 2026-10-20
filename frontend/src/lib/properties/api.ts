import { api } from '@/lib/api'
import type {
  ExcelImportMode,
  ExcelImportPreview,
  ExcelImportResult,
  Property,
  PropertyListResponse,
  PropertyStaffListResponse
} from '@/lib/properties/types'
import type { PropertyWritePayload } from '@/lib/properties/validation'

const excelForm = (file: File, mode: ExcelImportMode, propertyId?: number) => {
  const body = new FormData()
  body.append('file', file)
  body.append('mode', mode)
  if (propertyId) body.append('property_id', String(propertyId))
  return body
}

export const propertiesApi = {
  list() {
    return api.get<PropertyListResponse>('/api/properties/')
  },
  get(id: number) {
    return api.get<Property>(`/api/properties/${id}/`)
  },
  create(payload: PropertyWritePayload) {
    return api.post<Property>('/api/properties/', payload)
  },
  update(id: number, payload: Partial<PropertyWritePayload>) {
    return api.patch<Property>(`/api/properties/${id}/`, payload)
  },
  listStaff(propertyId: number) {
    return api.get<PropertyStaffListResponse>(`/api/properties/${propertyId}/staff/`)
  },
  assignStaff(propertyId: number, payload: { user_id: number; role?: string; reports_to_id?: number | null }) {
    return api.post<PropertyStaffListResponse>(`/api/properties/${propertyId}/staff/`, payload)
  },
  updateStaff(propertyId: number, userId: number, payload: { role?: string; reports_to_id?: number | null; is_active?: boolean }) {
    return api.patch<PropertyStaffListResponse>(`/api/properties/${propertyId}/staff/${userId}/`, payload)
  },
  removeStaff(propertyId: number, userId: number) {
    return api.delete<{ ok: boolean }>(`/api/properties/${propertyId}/staff/${userId}/`)
  },
  exportProperties() {
    return api.download('/api/properties/export/', 'properties_export.xlsx')
  },
  exportLocations(propertyId?: number) {
    return api.download('/api/locations/export/', 'locations_export.xlsx', {
      query: propertyId ? { property_id: propertyId } : undefined
    })
  },
  exportPortfolio(propertyId?: number) {
    return api.download('/api/properties/portfolio-export/', propertyId ? 'property_export.xlsx' : 'portfolio_export.xlsx', {
      query: propertyId ? { property_id: propertyId } : undefined
    })
  },
  downloadImportTemplate() {
    return api.download('/api/properties/import-template/', 'properties_locations_import_template.xlsx')
  },
  previewImport(file: File, mode: ExcelImportMode, propertyId?: number) {
    return api.post<ExcelImportPreview>('/api/properties/import/preview/', excelForm(file, mode, propertyId))
  },
  commitImport(file: File, mode: ExcelImportMode, propertyId?: number) {
    return api.post<ExcelImportResult>('/api/properties/import/', excelForm(file, mode, propertyId))
  }
}
