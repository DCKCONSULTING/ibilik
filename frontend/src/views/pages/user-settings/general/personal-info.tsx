'use client'

import { useEffect, useState } from 'react'

import { toast } from 'sonner'

import { useAuth } from '@/components/auth/auth-provider'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { isApiError } from '@/lib/api'
import { authApi } from '@/lib/auth/api'
import { accountPropertySummary, roleLabel } from '@/lib/auth/permissions'

const initialsFor = (name: string) =>
  name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map(part => part[0]?.toUpperCase() ?? '')
    .join('') || 'U'

const PersonalInfo = () => {
  const { user, refresh } = useAuth()
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!user) return
    setFirstName(user.first_name)
    setLastName(user.last_name)
  }, [user])

  if (!user) return null

  const displayName = user.display_name || user.username

  const save = async (event: React.FormEvent) => {
    event.preventDefault()
    setSaving(true)

    try {
      const updated = await authApi.updateMe({
        first_name: firstName.trim(),
        last_name: lastName.trim()
      })

      await refresh()
      toast.success('Personal information saved.')
      setFirstName(updated.first_name)
      setLastName(updated.last_name)
    } catch (err) {
      toast.error(isApiError(err) ? err.message : 'Unable to save personal information.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className='grid grid-cols-1 gap-10 lg:grid-cols-3'>
      <div className='flex flex-col space-y-1'>
        <h3 className='text-base font-semibold'>Personal Information</h3>
        <p className='text-muted-foreground text-sm'>Update your name. Your role and properties are assigned by an administrator.</p>
      </div>

      <form className='space-y-6 lg:col-span-2' onSubmit={event => void save(event)}>
        <div className='flex items-center gap-4'>
          <Avatar className='size-20 after:hidden'>
            <AvatarFallback className='text-lg'>{initialsFor(displayName)}</AvatarFallback>
          </Avatar>
          <div>
            <p className='font-medium'>{displayName}</p>
            <p className='text-muted-foreground text-sm'>@{user.username}</p>
          </div>
        </div>

        <div className='grid grid-cols-1 gap-6 sm:grid-cols-2'>
          <div className='flex flex-col items-start gap-2'>
            <Label htmlFor='settings-first-name'>First name</Label>
            <Input
              id='settings-first-name'
              value={firstName}
              onChange={event => setFirstName(event.target.value)}
              autoComplete='given-name'
            />
          </div>
          <div className='flex flex-col items-start gap-2'>
            <Label htmlFor='settings-last-name'>Last name</Label>
            <Input
              id='settings-last-name'
              value={lastName}
              onChange={event => setLastName(event.target.value)}
              autoComplete='family-name'
            />
          </div>
          <div className='flex flex-col items-start gap-2'>
            <Label htmlFor='settings-username'>Username</Label>
            <Input id='settings-username' value={user.username} disabled />
          </div>
          <div className='flex flex-col items-start gap-2'>
            <Label htmlFor='settings-role'>Role</Label>
            <Input id='settings-role' value={user.role_name || roleLabel(user.role)} disabled />
          </div>
          <div className='flex flex-col items-start gap-2 sm:col-span-2'>
            <Label htmlFor='settings-properties'>Properties</Label>
            <Input id='settings-properties' value={accountPropertySummary(user)} disabled />
          </div>
        </div>

        <div className='flex justify-end'>
          <Button type='submit' className='max-sm:w-full' disabled={saving}>
            {saving ? 'Saving…' : 'Save changes'}
          </Button>
        </div>
      </form>
    </div>
  )
}

export default PersonalInfo
