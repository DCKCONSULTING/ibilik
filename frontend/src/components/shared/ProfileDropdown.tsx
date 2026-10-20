'use client'

import Link from 'next/link'

import { LogOutIcon, SettingsIcon, UserIcon } from 'lucide-react'

import { useAuth } from '@/components/auth/auth-provider'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { accountPropertyHeading, accountPropertyNames, accountPropertySummary, roleLabel } from '@/lib/auth/permissions'

const initialsFor = (name: string) =>
  name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map(part => part[0]?.toUpperCase() ?? '')
    .join('') || 'U'

const ProfileDropdown = () => {
  const { user, logout } = useAuth()

  if (!user) return null

  const displayName = user.display_name || user.username
  const propertyNames = accountPropertyNames(user)
  const propertySummary = accountPropertySummary(user)

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={<Button variant='ghost' size='icon' className='relative rounded-full hover:bg-transparent' />}
      >
        <Avatar>
          <AvatarFallback>{initialsFor(displayName)}</AvatarFallback>
        </Avatar>
        <span className='ring-card absolute right-0 bottom-0 block size-2 rounded-full bg-green-600 ring-2' />
      </DropdownMenuTrigger>
      <DropdownMenuContent align='end' className='w-60'>
        <DropdownMenuGroup>
          <DropdownMenuLabel className='flex items-center gap-4 px-2 py-2.5 font-normal'>
            <div className='relative'>
              <Avatar className='size-10'>
                <AvatarFallback>{initialsFor(displayName)}</AvatarFallback>
              </Avatar>
              <span className='ring-card absolute right-0 bottom-0 block size-2 rounded-full bg-green-600 ring-2' />
            </div>
            <div className='flex flex-1 flex-col items-start'>
              <span className='text-foreground text-base font-semibold'>{displayName}</span>
              <span className='text-muted-foreground text-sm'>@{user.username}</span>
              <span className='text-muted-foreground text-xs'>{user.role_name || roleLabel(user.role)}</span>
            </div>
          </DropdownMenuLabel>
          <div className='text-muted-foreground px-2 pb-2 text-xs'>
            <p className='text-foreground font-medium'>
              {propertyNames.length ? accountPropertyHeading(propertyNames) : 'Properties'}
            </p>
            {propertyNames.length > 2 ? (
              <div>
                <p>{propertySummary}</p>
                <ul className='mt-1 space-y-0.5'>
                  {propertyNames.map(name => (
                    <li key={name}>{name}</li>
                  ))}
                </ul>
              </div>
            ) : propertyNames.length > 0 ? (
              <ul className='space-y-0.5'>
                {propertyNames.map(name => (
                  <li key={name}>{name}</li>
                ))}
              </ul>
            ) : (
              <p>{propertySummary}</p>
            )}
          </div>
        </DropdownMenuGroup>

        <DropdownMenuSeparator />

        <DropdownMenuGroup>
          <DropdownMenuItem render={<Link href='/pages/user-profile?view=profile' />}>
            <UserIcon />
            <span>My Account</span>
          </DropdownMenuItem>
          <DropdownMenuItem render={<Link href='/pages/user-settings?setting=general' />}>
            <SettingsIcon />
            <span>Settings</span>
          </DropdownMenuItem>
        </DropdownMenuGroup>

        <DropdownMenuSeparator />

        <DropdownMenuGroup>
          <DropdownMenuItem variant='destructive' onClick={() => void logout()}>
            <LogOutIcon />
            <span>Sign out</span>
          </DropdownMenuItem>
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export default ProfileDropdown
