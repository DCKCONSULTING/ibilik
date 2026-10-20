// Config Imports
import { brand } from '@/configs/brand'

// SVG Imports
import LogoSvg from '@/assets/svg/logo'

// Util Imports
import { cn } from '@/lib/utils'

const Logo = ({ className }: { className?: string }) => {
  return (
    <div className={cn('flex items-center gap-2.5', className)}>
      <LogoSvg className='size-8.5' />
      <span className='text-xl font-bold'>{brand.name}</span>
    </div>
  )
}

export default Logo
