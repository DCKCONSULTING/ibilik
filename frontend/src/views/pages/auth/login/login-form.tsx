'use client'

import { useState } from 'react'
import type { FormEvent } from 'react'

import { EyeIcon, EyeOffIcon } from 'lucide-react'

import { useAuth } from '@/components/auth/auth-provider'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { InputGroup, InputGroupAddon, InputGroupInput } from '@/components/ui/input-group'
import { isApiError } from '@/lib/api'

const LoginForm = () => {
  const { login } = useAuth()
  const [isVisible, setIsVisible] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)

    const formData = new FormData(event.currentTarget)
    const username = String(formData.get('username') ?? '').trim()
    const password = String(formData.get('password') ?? '')

    try {
      await login(username, password)
    } catch (err) {
      setError(isApiError(err) ? err.message : 'Unable to sign in with the provided credentials.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <FieldGroup className='gap-4'>
        {error && (
          <Alert variant='destructive'>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        <Field className='gap-2'>
          <FieldLabel htmlFor='username' className='leading-5'>
            Username
          </FieldLabel>
          <Input
            type='text'
            id='username'
            name='username'
            placeholder='Enter your username'
            required
            autoComplete='username'
            autoCapitalize='none'
            spellCheck={false}
          />
        </Field>
        <Field className='w-full gap-2'>
          <FieldLabel htmlFor='password' className='leading-5'>
            Password
          </FieldLabel>
          <InputGroup>
            <InputGroupInput
              id='password'
              name='password'
              type={isVisible ? 'text' : 'password'}
              placeholder='••••••••••••••••'
              required
              autoComplete='current-password'
            />
            <InputGroupAddon align='inline-end' className='pr-1.5'>
              <Button
                type='button'
                variant='ghost'
                size='icon'
                onClick={() => setIsVisible(prevState => !prevState)}
                className='text-muted-foreground rounded-l-none hover:bg-transparent'
              >
                {isVisible ? <EyeOffIcon /> : <EyeIcon />}
                <span className='sr-only'>{isVisible ? 'Hide password' : 'Show password'}</span>
              </Button>
            </InputGroupAddon>
          </InputGroup>
        </Field>
        <Field>
          <Button className='w-full' type='submit' disabled={isSubmitting}>
            {isSubmitting ? 'Signing in…' : 'Sign In'}
          </Button>
        </Field>
      </FieldGroup>
    </form>
  )
}

export default LoginForm
