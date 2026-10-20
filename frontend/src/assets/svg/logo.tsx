// React Imports
import type { SVGAttributes } from 'react'

const Logo = (props: SVGAttributes<SVGElement>) => {
  return (
    <svg width='1em' height='1em' viewBox='0 0 32 32' fill='none' xmlns='http://www.w3.org/2000/svg' {...props}>
      <rect width='32' height='32' rx='8' className='fill-primary' />
      <rect x='14' y='12' width='4' height='13' rx='1' className='fill-primary-foreground' />
      <circle cx='16' cy='8.5' r='2' className='fill-primary-foreground' />
    </svg>
  )
}

export default Logo
