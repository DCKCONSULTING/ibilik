'use client'

import { useState } from 'react'

import { Trash2Icon } from 'lucide-react'
import { toast } from 'sonner'

import { useAuth } from '@/components/auth/auth-provider'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogClose, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { isApiError } from '@/lib/api'
import { authApi } from '@/lib/auth/api'

const DangerZone = () => {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const [saving, setSaving] = useState(false)

  if (!user) return null

  const isSystemAdmin = user.is_superuser

  const deactivate = async () => {
    setSaving(true)

    try {
        await authApi.deactivateAccount()
      toast.success('Your account has been deactivated.')
      await logout().catch(() => undefined)
    } catch (err) {
      toast.error(isApiError(err) ? err.message : 'Unable to deactivate this account.')
      setSaving(false)
    }
  }

  return (
    <div className='grid grid-cols-1 gap-10 lg:grid-cols-3'>
      <div className='flex flex-col space-y-1'>
        <h3 className='text-base font-semibold'>Danger Zone</h3>
        <p className='text-muted-foreground text-sm'>
          Deactivating your account signs you out and blocks further sign-in until an administrator reactivates it.
        </p>
      </div>

      <div className='space-y-6 lg:col-span-2'>
        <Card>
          <CardContent>
            <div className='flex justify-between gap-4 max-lg:flex-col lg:items-center'>
              <div className='space-y-1'>
                <h3 className='text-sm font-medium'>Deactivate account</h3>
                <p className='text-muted-foreground text-sm'>
                  {isSystemAdmin
                    ? 'System Admin accounts cannot be deactivated from settings.'
                    : 'This action signs you out immediately. Your data stays in the system.'}
                </p>
              </div>
              <Dialog open={open} onOpenChange={setOpen}>
                <DialogTrigger
                  disabled={isSystemAdmin}
                  render={
                    <Button
                      variant='outline'
                      disabled={isSystemAdmin}
                      className='border-destructive! text-destructive! hover:bg-destructive/10! focus-visible:ring-destructive/20 dark:focus-visible:ring-destructive/40 max-lg:w-full'
                    />
                  }
                >
                  <Trash2Icon />
                  Deactivate
                </DialogTrigger>
                <DialogContent className='sm:max-w-md'>
                  <DialogHeader className='space-y-2'>
                    <DialogTitle>Deactivate account</DialogTitle>
                    <div className='text-muted-foreground text-sm'>
                      You will be signed out and will not be able to sign in until an administrator reactivates this
                      account.
                    </div>
                  </DialogHeader>
                  <div className='flex flex-col-reverse gap-4 sm:flex-row sm:justify-end'>
                    <DialogClose render={<Button variant='outline' />}>Cancel</DialogClose>
                    <Button variant='destructive' onClick={() => void deactivate()} disabled={saving}>
                      {saving ? 'Deactivating…' : 'Deactivate'}
                    </Button>
                  </div>
                </DialogContent>
              </Dialog>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

export default DangerZone
