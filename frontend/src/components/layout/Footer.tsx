// Config Imports
import { brand } from '@/configs/brand'

const Footer = () => {
  return (
    <footer>
      <div className='text-muted-foreground flex w-full items-center justify-between gap-3 px-4 py-3 max-sm:flex-col'>
        <p className='text-sm font-medium text-balance max-sm:text-center'>{brand.productName}</p>
        <p className='text-sm text-balance max-sm:text-center'>
          ©{new Date().getFullYear()} {brand.name}
        </p>
      </div>
    </footer>
  )
}

export default Footer
