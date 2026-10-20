export const occupancyBadgeClass = (occupancy?: string) => {
  if (occupancy === 'in_house') return 'border-transparent bg-amber-500/10 text-amber-800 dark:text-amber-400'
  if (occupancy === 'reserved' || occupancy === 'upcoming') return 'border-transparent bg-sky-500/10 text-sky-700 dark:text-sky-400'
  if (occupancy === 'free') return 'border-transparent bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'

  return ''
}

export const statusBadgeClass = (status: string) => {
  if (status === 'available') return 'border-transparent bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
  if (status === 'dirty') return 'border-transparent bg-orange-500/10 text-orange-800 dark:text-orange-400'
  if (status === 'cleaning') return 'border-transparent bg-sky-500/10 text-sky-700 dark:text-sky-400'
  if (status === 'inspection') return 'border-transparent bg-violet-500/10 text-violet-700 dark:text-violet-400'
  if (status === 'maintenance' || status === 'out_of_order' || status === 'inactive') return 'text-destructive'

  return ''
}
