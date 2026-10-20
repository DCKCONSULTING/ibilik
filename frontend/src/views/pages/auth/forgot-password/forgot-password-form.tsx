'use client'

// React Imports
import type { FormEvent } from 'react'

// Next Imports
import { useRouter } from 'next/navigation'

// Component Import
import { Button } from '@/components/ui/button'
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'

const ForgotPasswordForm = () => {
  const router = useRouter()

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    router.push('/pages/auth/reset-password')
  }

  return (
    <form onSubmit={handleSubmit}>
      <FieldGroup className='gap-4'>
        <Field>
          <FieldLabel className='leading-5' htmlFor='userEmail'>
            Email address
          </FieldLabel>
          <Input
            type='email'
            id='userEmail'
            name='email'
            placeholder='Enter your work email'
            required
            autoComplete='email'
          />
        </Field>
        <Field>
          <Button className='w-full' type='submit'>
            Send Reset Link
          </Button>
        </Field>
      </FieldGroup>
    </form>
  )
}

export default ForgotPasswordForm
