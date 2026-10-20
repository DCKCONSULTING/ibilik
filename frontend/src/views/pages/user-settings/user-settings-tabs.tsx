'use client'

import { useEffect } from 'react'

import { parseAsString, useQueryState } from 'nuqs'

import UserGeneral from '@/views/pages/user-settings/general'

const UserSettingsTabs = () => {
  const [, setActiveSetting] = useQueryState(
    'setting',
    parseAsString.withDefault('general').withOptions({
      history: 'replace',
      shallow: true,
      clearOnDefault: false
    })
  )

  useEffect(() => {
    setActiveSetting('general')
  }, [setActiveSetting])

  return (
    <div className='w-full'>
      <UserGeneral />
    </div>
  )
}

export default UserSettingsTabs
