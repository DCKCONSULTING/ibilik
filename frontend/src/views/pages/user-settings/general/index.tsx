import { Separator } from '@/components/ui/separator'

import DangerZone from '@/views/pages/user-settings/general/danger-zone'
import EmailPass from '@/views/pages/user-settings/general/email-password'
import PersonalInfo from '@/views/pages/user-settings/general/personal-info'

const UserGeneral = () => {
  return (
    <section className='py-3'>
      <PersonalInfo />
      <Separator className='my-10' />
      <EmailPass />
      <Separator className='my-10' />
      <DangerZone />
    </section>
  )
}

export default UserGeneral
