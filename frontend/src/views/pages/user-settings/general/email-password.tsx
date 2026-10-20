'use client'

import { useEffect, useMemo, useState } from 'react'

import { CheckIcon, EyeIcon, EyeOffIcon, MailIcon, XIcon } from 'lucide-react'
import { toast } from 'sonner'

import { useAuth } from '@/components/auth/auth-provider'
import { Button } from '@/components/ui/button'
import { InputGroup, InputGroupAddon, InputGroupInput } from '@/components/ui/input-group'
import { Label } from '@/components/ui/label'
import { isApiError } from '@/lib/api'
import { authApi } from '@/lib/auth/api'
import { cn } from '@/lib/utils'

const requirements = [
  { regex: /.{8,}/, text: 'At least 8 characters' },
  { regex: /[a-z]/, text: 'At least 1 lowercase letter' },
  { regex: /[A-Z]/, text: 'At least 1 uppercase letter' },
  { regex: /[0-9]/, text: 'At least 1 number' }
]

const EmailPass = () => {
  const { user, refresh } = useAuth()
  const [email, setEmail] = useState('')
  const [currentPassword, setCurrentPassword] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [isVisible, setIsVisible] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!user) return
    setEmail(user.email)
  }, [user])

  const strength = requirements.map(req => ({
    met: req.regex.test(password),
    text: req.text
  }))

  const strengthScore = useMemo(() => strength.filter(req => req.met).length, [strength])

  const getColor = (score: number) => {
    if (score === 0) return 'bg-border'
    if (score <= 1) return 'bg-destructive'
    if (score <= 2) return 'bg-orange-500'
    if (score === 3) return 'bg-yellow-400'

    return 'bg-green-500'
  }

  const getText = (score: number) => {
    if (score === 0) return 'Enter a password'
    if (score <= 2) return 'Weak password'
    if (score === 3) return 'Strong password'

    return 'Very strong password'
  }

  if (!user) return null

  const save = async (event: React.FormEvent) => {
    event.preventDefault()
    setSaving(true)

    try {
      const nextEmail = email.trim()
      const emailChanged = nextEmail !== (user.email || '')
      const changingPassword = Boolean(password || currentPassword || confirmPassword)

      if (emailChanged) {
        if (!nextEmail.includes('@')) {
          toast.error('Enter a valid email address.')
          setSaving(false)

          return
        }

        await authApi.updateMe({ email: nextEmail })
      }

      if (changingPassword) {
        if (!currentPassword) {
          toast.error('Enter your current password to change it.')
          setSaving(false)

          return
        }

        if (password !== confirmPassword) {
          toast.error('New password and confirmation do not match.')
          setSaving(false)

          return
        }

        if (strengthScore < requirements.length) {
          toast.error('Choose a stronger password.')
          setSaving(false)

          return
        }

        await authApi.changePassword({ current_password: currentPassword, password })
        setCurrentPassword('')
        setPassword('')
        setConfirmPassword('')
      }

      if (!emailChanged && !changingPassword) {
        toast.error('Update your email or enter a new password.')
        setSaving(false)

        return
      }

      await refresh()
      toast.success(changingPassword ? 'Account security settings saved.' : 'Email saved.')
    } catch (err) {
      toast.error(isApiError(err) ? err.message : 'Unable to save email or password.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className='grid grid-cols-1 gap-10 lg:grid-cols-3'>
      <div className='flex flex-col space-y-1'>
        <h3 className='text-base font-semibold'>Email & Password</h3>
        <p className='text-muted-foreground text-sm'>Update the email on this account or change your password.</p>
      </div>

      <form className='space-y-6 lg:col-span-2' onSubmit={event => void save(event)}>
        <div className='w-full space-y-2'>
          <Label htmlFor='settings-email' className='gap-1'>
            Email<span className='text-destructive'>*</span>
          </Label>
          <InputGroup>
            <InputGroupInput
              id='settings-email'
              type='email'
              placeholder='Email address'
              value={email}
              onChange={event => setEmail(event.target.value)}
              autoComplete='email'
              required
            />
            <InputGroupAddon align='inline-end' className='pr-2.75'>
              <MailIcon className='size-4' />
              <span className='sr-only'>Email</span>
            </InputGroupAddon>
          </InputGroup>
        </div>
        <div className='w-full space-y-2'>
          <Label htmlFor='current-password'>Current password</Label>
          <InputGroup>
            <InputGroupInput
              id='current-password'
              type={isVisible ? 'text' : 'password'}
              placeholder='Required to change password'
              value={currentPassword}
              onChange={event => setCurrentPassword(event.target.value)}
              autoComplete='current-password'
            />
            <InputGroupAddon align='inline-end' className='pr-1.5'>
              <Button
                type='button'
                variant='ghost'
                size='icon'
                onClick={() => setIsVisible(current => !current)}
                className='text-muted-foreground focus-visible:ring-ring/50 rounded-l-none hover:bg-transparent'
              >
                {isVisible ? <EyeOffIcon /> : <EyeIcon />}
                <span className='sr-only'>{isVisible ? 'Hide password' : 'Show password'}</span>
              </Button>
            </InputGroupAddon>
          </InputGroup>
        </div>
        <div className='w-full space-y-2'>
          <Label htmlFor='new-password'>New password</Label>
          <InputGroup className='mb-3'>
            <InputGroupInput
              id='new-password'
              type={isVisible ? 'text' : 'password'}
              placeholder='Leave blank to keep the current password'
              value={password}
              onChange={event => setPassword(event.target.value)}
              autoComplete='new-password'
            />
            <InputGroupAddon align='inline-end' className='pr-1.5'>
              <Button
                type='button'
                variant='ghost'
                size='icon'
                onClick={() => setIsVisible(current => !current)}
                className='text-muted-foreground focus-visible:ring-ring/50 rounded-l-none hover:bg-transparent'
              >
                {isVisible ? <EyeOffIcon /> : <EyeIcon />}
                <span className='sr-only'>{isVisible ? 'Hide password' : 'Show password'}</span>
              </Button>
            </InputGroupAddon>
          </InputGroup>

          <div className='mb-4 flex h-1 w-full gap-1'>
            {Array.from({ length: 4 }).map((_, index) => (
              <span
                key={index}
                className={cn(
                  'h-full flex-1 rounded-full transition-all duration-500 ease-out',
                  index < strengthScore ? getColor(strengthScore) : 'bg-border'
                )}
              />
            ))}
          </div>

          <p className='text-foreground text-sm font-medium'>{getText(strengthScore)}. Must contain:</p>

          <ul className='mb-4 space-y-1.5'>
            {strength.map(req => (
              <li key={req.text} className='flex items-center gap-2'>
                {req.met ? (
                  <CheckIcon className='size-4 text-green-600 dark:text-green-400' />
                ) : (
                  <XIcon className='text-muted-foreground size-4' />
                )}
                <span className={cn('text-xs', req.met ? 'text-green-600 dark:text-green-400' : 'text-muted-foreground')}>
                  {req.text}
                </span>
              </li>
            ))}
          </ul>
        </div>
        <div className='w-full space-y-2'>
          <Label htmlFor='confirm-password'>Confirm new password</Label>
          <InputGroup>
            <InputGroupInput
              id='confirm-password'
              type={isVisible ? 'text' : 'password'}
              placeholder='Confirm new password'
              value={confirmPassword}
              onChange={event => setConfirmPassword(event.target.value)}
              autoComplete='new-password'
            />
          </InputGroup>
        </div>

        <div className='mt-6 flex justify-end'>
          <Button type='submit' className='max-sm:w-full' disabled={saving}>
            {saving ? 'Saving…' : 'Save changes'}
          </Button>
        </div>
      </form>
    </div>
  )
}

export default EmailPass
