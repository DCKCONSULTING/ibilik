import { brand } from '@/configs/brand'

const themeConfig = {
  templateName: brand.name,
  productName: brand.productName,
  homePageUrl: '/dashboard'
} as const

export default themeConfig
