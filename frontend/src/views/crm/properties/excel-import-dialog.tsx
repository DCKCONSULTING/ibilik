'use client'

import { useRef, useState } from 'react'

import { toast } from 'sonner'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog'
import { Field, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { isApiError } from '@/lib/api'
import { propertiesApi } from '@/lib/properties/api'
import type { ExcelImportMode, ExcelImportPreview } from '@/lib/properties/types'

type ExcelImportDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  onImported: () => void
  propertyId?: number
  defaultMode?: ExcelImportMode
}

const ExcelImportDialog = ({
  open,
  onOpenChange,
  onImported,
  propertyId,
  defaultMode = 'portfolio'
}: ExcelImportDialogProps) => {
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [mode, setMode] = useState<ExcelImportMode>(defaultMode)
  const [preview, setPreview] = useState<ExcelImportPreview | null>(null)
  const [loading, setLoading] = useState(false)
  const [committing, setCommitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const reset = () => {
    setFile(null)
    setPreview(null)
    setError(null)
    setLoading(false)
    setCommitting(false)
    if (inputRef.current) inputRef.current.value = ''
  }

  const close = () => {
    reset()
    onOpenChange(false)
  }

  const upload = async (nextFile = file) => {
    if (!nextFile) {
      setError('Choose an .xlsx file first.')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const payload = await propertiesApi.previewImport(nextFile, mode, propertyId)
      setPreview(payload)
    } catch (err) {
      setPreview(null)
      setError(isApiError(err) ? err.message : 'Unable to validate this workbook.')
    } finally {
      setLoading(false)
    }
  }

  const confirm = async () => {
    if (!file || !preview?.valid) return

    setCommitting(true)
    setError(null)

    try {
      const result = await propertiesApi.commitImport(file, mode, propertyId)
      toast.success(
        `Imported ${result.created_properties.length + result.updated_properties.length} properties and ${result.created_locations.length + result.updated_locations.length} locations.`
      )
      onImported()
      close()
    } catch (err) {
      setError(isApiError(err) ? err.message : 'Unable to import this workbook.')
    } finally {
      setCommitting(false)
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={next => {
        if (!next) close()
        else onOpenChange(true)
      }}
    >
      <DialogContent className='max-h-[min(100dvh,46rem)] overflow-y-auto sm:max-w-3xl'>
        <DialogHeader>
          <DialogTitle>{propertyId ? 'Import Locations Excel' : 'Import Excel'}</DialogTitle>
        </DialogHeader>
        <div className='space-y-4'>
          <div className='grid gap-4 sm:grid-cols-2'>
            <Field>
              <FieldLabel htmlFor='excel-file'>Excel file</FieldLabel>
              <Input
                ref={inputRef}
                id='excel-file'
                type='file'
                accept='.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                onChange={event => {
                  const next = event.target.files?.[0] ?? null
                  setFile(next)
                  setPreview(null)
                  setError(null)
                }}
              />
            </Field>
            {!propertyId && (
              <Field>
                <FieldLabel>Import mode</FieldLabel>
                <Select value={mode} onValueChange={value => value && setMode(value as ExcelImportMode)}>
                  <SelectTrigger className='w-full'>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value='portfolio'>Portfolio (properties and locations)</SelectItem>
                    <SelectItem value='properties'>Properties only</SelectItem>
                    <SelectItem value='locations'>Locations only</SelectItem>
                  </SelectContent>
                </Select>
              </Field>
            )}
          </div>
          <div className='flex flex-wrap gap-2'>
            <Button onClick={() => void upload()} disabled={loading || !file}>
              {loading ? 'Validating…' : 'Validate workbook'}
            </Button>
            <Button
              variant='outline'
              onClick={() =>
                void propertiesApi.downloadImportTemplate().catch(err => {
                  toast.error(isApiError(err) ? err.message : 'Unable to download the template.')
                })
              }
            >
              Download template
            </Button>
          </div>
          {error && (
            <Alert variant='destructive'>
              <AlertTitle>Import error</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          {preview && (
            <div className='space-y-4'>
              <div className='grid gap-2 text-sm sm:grid-cols-2'>
                <p>
                  Properties: {preview.summary.properties_create} new, {preview.summary.properties_update} updates,{' '}
                  {preview.summary.properties_errors} errors.
                </p>
                <p>
                  Locations: {preview.summary.locations_create} new, {preview.summary.locations_update} updates,{' '}
                  {preview.summary.locations_errors} errors.
                </p>
              </div>
              {preview.issues.length > 0 && (
                <div className='overflow-x-auto'>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Level</TableHead>
                        <TableHead>Sheet</TableHead>
                        <TableHead>Row</TableHead>
                        <TableHead>Column</TableHead>
                        <TableHead>Message</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {preview.issues.map((issue, index) => (
                        <TableRow key={`${issue.sheet}-${issue.row}-${issue.column}-${index}`}>
                          <TableCell className={issue.level === 'error' ? 'text-destructive' : ''}>{issue.level}</TableCell>
                          <TableCell>{issue.sheet}</TableCell>
                          <TableCell>{issue.row}</TableCell>
                          <TableCell>{issue.column || '—'}</TableCell>
                          <TableCell>{issue.message}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
              {!preview.valid && (
                <Alert variant='destructive'>
                  <AlertDescription>Nothing will be imported until every required row is valid.</AlertDescription>
                </Alert>
              )}
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant='outline' onClick={close} disabled={committing}>
            Cancel
          </Button>
          <Button onClick={() => void confirm()} disabled={!preview?.valid || committing}>
            {committing ? 'Importing…' : 'Confirm import'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default ExcelImportDialog
