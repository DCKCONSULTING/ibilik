'use client'

import { useEffect, useMemo, useState } from 'react'

import { PlusIcon, SearchIcon } from 'lucide-react'
import { toast } from 'sonner'

import { useAuth } from '@/components/auth/auth-provider'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { InputGroup, InputGroupAddon, InputGroupInput } from '@/components/ui/input-group'
import { isApiError } from '@/lib/api'
import { pipelineApi } from '@/lib/pipeline/api'
import type { Opportunity, PipelineStage } from '@/lib/pipeline/types'
import { PIPELINE_STAGES } from '@/lib/pipeline/types'
import { formatPipelineValue } from '@/lib/pipeline/validation'
import { cn } from '@/lib/utils'

import AddOpportunityDialog from './add-opportunity-dialog'
import OpportunityCard from './opportunity-card'

const emptyCounts = (): Record<PipelineStage, number> => ({
  new: 0,
  qualified: 0,
  quoted: 0,
  negotiating: 0,
  won: 0,
  lost: 0
})

const PipelinePageView = () => {
  const { can } = useAuth()
  const [opportunities, setOpportunities] = useState<Opportunity[]>([])
  const [stageCounts, setStageCounts] = useState(emptyCounts)
  const [totalValue, setTotalValue] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [errorStatus, setErrorStatus] = useState<number | null>(null)
  const [search, setSearch] = useState('')
  const [addOpen, setAddOpen] = useState(false)
  const [draggingOver, setDraggingOver] = useState<PipelineStage | null>(null)
  const canAdd = can(['opportunities.add_opportunity', 'cases.add_case'])
  const canChange = can(['opportunities.change_opportunity', 'cases.change_case'])

  useEffect(() => {
    let mounted = true

    const handle = window.setTimeout(() => {
      pipelineApi
        .list({ search: search.trim() || undefined, page_size: 200 })
        .then(payload => {
          if (!mounted) return

          setOpportunities(payload.results)
          setStageCounts({ ...emptyCounts(), ...payload.stage_counts })
          setTotalValue(payload.total_value)
          setError(null)
          setErrorStatus(null)
        })
        .catch(err => {
          if (!mounted) return

          setError(isApiError(err) ? err.message : 'Unable to load the CRM pipeline.')
          setErrorStatus(isApiError(err) ? err.status : 0)
        })
        .finally(() => {
          if (!mounted) return

          setLoading(false)
        })
    }, 250)

    return () => {
      mounted = false
      window.clearTimeout(handle)
    }
  }, [search])

  const columns = useMemo(() => {
    return PIPELINE_STAGES.map(stage => ({
      ...stage,
      items: opportunities.filter(item => item.stage === stage.id),
      count: stageCounts[stage.id]
    }))
  }, [opportunities, stageCounts])

  const moveOpportunity = async (opportunityId: number, stage: PipelineStage) => {
    const current = opportunities.find(item => item.id === opportunityId)

    if (!current || current.stage === stage || !canChange) return

    setOpportunities(items => items.map(item => (item.id === opportunityId ? { ...item, stage, stage_label: stage } : item)))
    setStageCounts(counts => ({
      ...counts,
      [current.stage]: Math.max(0, counts[current.stage] - 1),
      [stage]: counts[stage] + 1
    }))

    try {
      const updated = await pipelineApi.updateStage(opportunityId, stage)

      setOpportunities(items => items.map(item => (item.id === opportunityId ? updated : item)))
    } catch (err) {
      setOpportunities(items => items.map(item => (item.id === opportunityId ? current : item)))
      setStageCounts(counts => ({
        ...counts,
        [stage]: Math.max(0, counts[stage] - 1),
        [current.stage]: counts[current.stage] + 1
      }))
      toast.error(isApiError(err) ? err.message : 'Unable to move this pipeline record.')
    }
  }

  return (
    <div className='flex flex-col gap-6'>
      <div className='flex flex-wrap items-start justify-between gap-3'>
        <div>
          <h1 className='text-2xl font-semibold'>CRM Pipeline</h1>
          <p className='text-muted-foreground text-sm'>
            Sales stages for customer cases, from first request through won or lost.
          </p>
        </div>
        <div className='flex flex-wrap items-center gap-3'>
          {totalValue && (
            <div className='text-right'>
              <p className='text-muted-foreground text-xs'>Pipeline value</p>
              <p className='text-foreground text-sm font-semibold'>{formatPipelineValue(totalValue)}</p>
            </div>
          )}
          {canAdd && (
            <Button onClick={() => setAddOpen(true)}>
              <PlusIcon />
              New case
            </Button>
          )}
        </div>
      </div>

      <div className='grid gap-2 sm:grid-cols-3 xl:grid-cols-6'>
        {PIPELINE_STAGES.map(stage => (
          <div key={stage.id} className='bg-muted/40 rounded-lg px-3 py-2'>
            <p className='text-muted-foreground text-xs'>{stage.label}</p>
            <p className='text-foreground text-lg font-semibold'>{stageCounts[stage.id]}</p>
          </div>
        ))}
      </div>

      <InputGroup className='max-w-md'>
        <InputGroupAddon>
          <SearchIcon className='size-4' />
          <span className='sr-only'>Search</span>
        </InputGroupAddon>
        <InputGroupInput
          type='search'
          placeholder='Search case number, customer, phone, email, or title'
          value={search}
          onChange={event => setSearch(event.target.value)}
        />
      </InputGroup>

      {loading && (
        <p className='text-muted-foreground text-sm'>Loading CRM pipeline…</p>
      )}

      {!loading && error && (
        <Alert variant='destructive'>
          <AlertDescription>
            {errorStatus === 403
              ? 'You do not have permission to view the CRM pipeline.'
              : error}
          </AlertDescription>
        </Alert>
      )}

      {!loading && !error && opportunities.length === 0 && (
        <p className='text-muted-foreground text-sm'>No cases match the current filters.</p>
      )}

      {!loading && !error && opportunities.length > 0 && (
        <div className='flex min-h-[32rem] gap-3 overflow-x-auto pb-2'>
          {columns.map(column => (
            <section
              key={column.id}
              onDragOver={event => {
                if (!canChange) return

                event.preventDefault()
                setDraggingOver(column.id)
              }}
              onDragLeave={() => setDraggingOver(current => (current === column.id ? null : current))}
              onDrop={event => {
                event.preventDefault()
                setDraggingOver(null)

                const opportunityId = Number(event.dataTransfer.getData('text/plain'))

                if (Number.isInteger(opportunityId)) {
                  void moveOpportunity(opportunityId, column.id)
                }
              }}
              className={cn(
                'bg-muted/30 flex w-72 shrink-0 flex-col rounded-xl border p-3',
                draggingOver === column.id && 'border-foreground/30 bg-muted/60'
              )}
            >
              <div className='mb-3 flex items-center justify-between gap-2'>
                <h2 className='text-sm font-semibold'>{column.label}</h2>
                <span className='text-muted-foreground text-xs'>{column.count}</span>
              </div>
              <div className='flex min-h-40 flex-1 flex-col gap-2'>
                {column.items.map(opportunity => (
                  <OpportunityCard key={opportunity.id} opportunity={opportunity} disabled={!canChange} />
                ))}
                {!loading && column.items.length === 0 && (
                  <p className='text-muted-foreground px-1 text-xs'>No cases in this stage.</p>
                )}
              </div>
            </section>
          ))}
        </div>
      )}

      <AddOpportunityDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        onCreated={opportunity => {
          setOpportunities(current => [opportunity, ...current.filter(item => item.id !== opportunity.id)])
          setStageCounts(counts => ({
            ...counts,
            [opportunity.stage]: counts[opportunity.stage] + 1
          }))
        }}
      />
    </div>
  )
}

export default PipelinePageView
