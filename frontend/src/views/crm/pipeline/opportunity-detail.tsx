'use client'

import { useEffect, useState } from 'react'

import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import { toast } from 'sonner'

import { useAuth } from '@/components/auth/auth-provider'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { isApiError } from '@/lib/api'
import type { Channel, Customer } from '@/lib/customers/types'
import { channelLabel } from '@/lib/customers/validation'
import { formatDueAt, formatRelativeTime } from '@/lib/datetime'
import { casesApi, pipelineApi } from '@/lib/pipeline/api'
import type { CaseFollowUp, Opportunity, WorkflowAction } from '@/lib/pipeline/types'
import { formatPipelineValue, staffName, workflowActionLabel } from '@/lib/pipeline/validation'
import { cn } from '@/lib/utils'
import CustomerDetailSheet from '@/views/crm/customers/customer-detail-sheet'

import CasePaymentsSection from '@/views/crm/payments/case-payments-section'

import CaseFollowUpDialog from './case-follow-up-dialog'
import {
  AddOpportunityNoteDialog,
  OpportunityHistorySheet,
  TransferOpportunityDialog
} from './opportunity-action-dialogs'
import QuoteOpportunityDialog from './quote-opportunity-dialog'

const senderLabel = (value: string) => {
  if (value === 'bot') return 'AI Bot'
  if (value === 'staff') return 'Staff'
  if (value === 'system') return 'System'

  return 'Customer'
}

const isChannel = (value: string | null | undefined): value is Channel =>
  value === 'website' || value === 'whatsapp' || value === 'facebook'

const customerFromOpportunity = (opportunity: Opportunity): Customer => ({
  id: opportunity.customer.id,
  name: opportunity.customer.name,
  email: opportunity.customer.email,
  phone: opportunity.customer.phone,
  status: opportunity.customer.status ?? 'lead',
  sources: isChannel(opportunity.source) ? [opportunity.source] : [],
  properties: opportunity.property ? [opportunity.property] : [],
  last_contact_at: null,
  reply_channels: [],
  identities: opportunity.customer.identities
})

const followUpStatusClass = (status: string) => {
  if (status === 'overdue') return 'text-destructive font-medium'
  if (status === 'completed') return 'text-muted-foreground'
  if (status === 'cancelled') return 'text-muted-foreground line-through'

  return ''
}

const OpportunityDetailView = () => {
  const params = useParams<{ id: string }>()
  const router = useRouter()
  const opportunityId = Number(params.id)
  const validId = Number.isInteger(opportunityId) && opportunityId > 0
  const { can, user } = useAuth()
  const [opportunity, setOpportunity] = useState<Opportunity | null>(null)
  const [loading, setLoading] = useState(validId)
  const [error, setError] = useState<string | null>(validId ? null : 'Case not found.')
  const [errorStatus, setErrorStatus] = useState<number | null>(validId ? null : 404)
  const [acting, setActing] = useState(false)
  const [quoteOpen, setQuoteOpen] = useState(false)
  const [transferOpen, setTransferOpen] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [noteOpen, setNoteOpen] = useState(false)
  const [customerOpen, setCustomerOpen] = useState(false)
  const [followUpOpen, setFollowUpOpen] = useState(false)
  const [editingFollowUp, setEditingFollowUp] = useState<CaseFollowUp | null>(null)
  const canChange = can(['opportunities.change_opportunity', 'cases.change_case'])
  const canViewUsers = can('users.view_user')

  const loadCase = () => casesApi.get(opportunityId)

  useEffect(() => {
    if (!validId) return

    let mounted = true

    casesApi
      .get(opportunityId)
      .then(payload => {
        if (!mounted) return

        setOpportunity(payload)
        setError(null)
        setErrorStatus(null)
      })
      .catch(err => {
        if (!mounted) return

        setOpportunity(null)
        setErrorStatus(isApiError(err) ? err.status : 0)
        setError(isApiError(err) ? err.message : 'Unable to load this case.')
      })
      .finally(() => {
        if (!mounted) return

        setLoading(false)
      })

    return () => {
      mounted = false
    }
  }, [opportunityId, validId])

  const runAction = async (action: WorkflowAction) => {
    if (!opportunity) return

    if (action === 'quote') {
      setQuoteOpen(true)

      return
    }

    setActing(true)

    try {
      const updated = await pipelineApi.performAction(opportunity.id, { action })

      setOpportunity(updated)
      toast.success(`${workflowActionLabel(action)} completed.`)
    } catch (err) {
      toast.error(isApiError(err) ? err.message : 'Unable to complete this workflow action.')
    } finally {
      setActing(false)
    }
  }

  const refreshCase = async () => {
    const updated = await loadCase()

    setOpportunity(updated)

    return updated
  }

  const completeFollowUp = async (followUp: CaseFollowUp) => {
    try {
      await casesApi.completeFollowUp(opportunityId, followUp.id)
      await refreshCase()
      toast.success('Follow-up completed.')
    } catch (err) {
      toast.error(isApiError(err) ? err.message : 'Unable to complete this follow-up.')
    }
  }

  const cancelFollowUp = async (followUp: CaseFollowUp) => {
    try {
      await casesApi.cancelFollowUp(opportunityId, followUp.id)
      await refreshCase()
      toast.success('Follow-up cancelled.')
    } catch (err) {
      toast.error(isApiError(err) ? err.message : 'Unable to cancel this follow-up.')
    }
  }

  const openConversation = () => {
    const conversationId = opportunity?.conversation_id || opportunity?.conversation?.id

    if (!conversationId) {
      toast.error('This case has no linked conversation.')

      return
    }

    router.push(`/apps/mail?conversation=${conversationId}`)
  }

  if (loading) {
    return <p className='text-muted-foreground text-sm'>Loading case…</p>
  }

  if (error || !opportunity) {
    return (
      <div className='flex flex-col gap-4'>
        <Button render={<Link href='/opportunities' />} nativeButton={false} variant='ghost' className='w-fit px-0'>
          ← CRM Pipeline
        </Button>
        <Alert variant='destructive'>
          <AlertTitle>{errorStatus === 403 ? 'Permission denied' : errorStatus === 404 ? 'Not found' : 'API error'}</AlertTitle>
          <AlertDescription>{error ?? 'Unable to load this case.'}</AlertDescription>
        </Alert>
      </div>
    )
  }

  const messages = opportunity.messages ?? opportunity.conversation?.messages ?? []
  const workflowActions = (opportunity.allowed_actions ?? []).filter(action => action !== 'quote')
  const hasConversation = Boolean(opportunity.conversation_id || opportunity.conversation?.id)
  const assigned = staffName(opportunity)
  const followUps = opportunity.follow_ups ?? []
  const activities = opportunity.activities ?? []
  const nextFollowUp = opportunity.next_follow_up

  return (
    <div className='flex flex-col gap-6'>
      <div>
        <Button render={<Link href='/opportunities' />} nativeButton={false} variant='ghost' className='mb-3 w-fit px-0'>
          ← CRM Pipeline
        </Button>
        <div className='flex flex-wrap items-start justify-between gap-3'>
          <div>
            <p className='text-muted-foreground text-sm font-medium tracking-wide'>{opportunity.case_number}</p>
            <button
              type='button'
              className='text-foreground text-2xl font-semibold hover:underline'
              onClick={() => setCustomerOpen(true)}
            >
              {opportunity.customer.name}
            </button>
            <p className='text-muted-foreground mt-1 text-sm'>{opportunity.title}</p>
          </div>
          <div className='flex flex-col items-end gap-1'>
            <Badge variant='outline' className='h-7 px-3 text-sm'>
              {opportunity.stage_label}
            </Badge>
            <p className='text-muted-foreground text-xs'>
              {opportunity.source_label || (opportunity.source ? channelLabel(opportunity.source) : 'Unknown source')}
            </p>
          </div>
        </div>
        <div className='mt-4 flex flex-wrap gap-2'>
          <Button type='button' disabled={!canChange || acting} onClick={() => setQuoteOpen(true)}>
            Quote
          </Button>
          {workflowActions.map(action => (
            <Button
              key={action}
              type='button'
              variant='outline'
              disabled={!canChange || acting}
              onClick={() => void runAction(action)}
            >
              {workflowActionLabel(action)}
            </Button>
          ))}
          <Button type='button' variant='outline' disabled={!canChange} onClick={() => setTransferOpen(true)}>
            Transfer
          </Button>
          <Button type='button' variant='outline' onClick={() => setHistoryOpen(true)}>
            History
          </Button>
          <Button type='button' variant='outline' disabled={!hasConversation} onClick={openConversation}>
            Open conversation
          </Button>
          <Button type='button' variant='outline' disabled={!canChange} onClick={() => setNoteOpen(true)}>
            Add note
          </Button>
        </div>
      </div>

      <div className='grid gap-4 xl:grid-cols-2'>
        <section className='bg-card rounded-xl border p-5'>
          <h2 className='text-sm font-semibold tracking-wide uppercase'>Customer request</h2>
          <p className='text-foreground mt-3 whitespace-pre-wrap'>
            {opportunity.original_request || opportunity.request || opportunity.description || 'No customer request is linked yet.'}
          </p>
        </section>

        <aside className='bg-card rounded-xl border p-5'>
          <h2 className='text-sm font-semibold tracking-wide uppercase'>Case information</h2>
          <dl className='mt-3 grid gap-3 text-sm sm:grid-cols-2'>
            <div>
              <dt className='text-muted-foreground'>Customer</dt>
              <dd className='font-medium'>{opportunity.customer.name}</dd>
            </div>
            <div>
              <dt className='text-muted-foreground'>Property</dt>
              <dd className='font-medium'>{opportunity.property?.name ?? 'No property'}</dd>
            </div>
            <div>
              <dt className='text-muted-foreground'>Staff</dt>
              <dd className='font-medium'>{assigned ?? 'Unassigned'}</dd>
            </div>
            <div>
              <dt className='text-muted-foreground'>Source</dt>
              <dd className='font-medium'>
                {opportunity.source_label || (opportunity.source ? channelLabel(opportunity.source) : 'Not linked')}
              </dd>
            </div>
            <div>
              <dt className='text-muted-foreground'>Stage</dt>
              <dd className='font-medium'>{opportunity.stage_label}</dd>
            </div>
            <div>
              <dt className='text-muted-foreground'>Value</dt>
              <dd className='font-medium'>{formatPipelineValue(opportunity.value) || '—'}</dd>
            </div>
            <div className='sm:col-span-2'>
              <dt className='text-muted-foreground'>Next follow-up</dt>
              <dd className={cn('font-medium', nextFollowUp?.status === 'overdue' && 'text-destructive')}>
                {nextFollowUp
                  ? `${nextFollowUp.title} — ${formatDueAt(nextFollowUp.due_at) || 'No due date'}${nextFollowUp.status === 'overdue' ? ' (Overdue)' : ''}`
                  : 'No pending follow-up'}
              </dd>
            </div>
          </dl>
          {opportunity.finance_status === 'sent' && (
            <p className='text-muted-foreground mt-3 text-xs'>
              Sent to finance. A dedicated finance module is not implemented yet; this is workflow state only.
            </p>
          )}
          {opportunity.quote_notes && (
            <div className='mt-4'>
              <p className='text-muted-foreground text-sm'>Quote notes</p>
              <p className='text-sm whitespace-pre-wrap'>{opportunity.quote_notes}</p>
            </div>
          )}
          {opportunity.staff_notes && (
            <div className='mt-4'>
              <p className='text-muted-foreground text-sm'>Staff notes</p>
              <p className='text-sm whitespace-pre-wrap'>{opportunity.staff_notes}</p>
            </div>
          )}
        </aside>
      </div>

      <section className='bg-card rounded-xl border p-5'>
        <div className='mb-3 flex flex-wrap items-center justify-between gap-2'>
          <h2 className='text-sm font-semibold tracking-wide uppercase'>Follow-ups</h2>
          <Button
            type='button'
            size='sm'
            disabled={!canChange}
            onClick={() => {
              setEditingFollowUp(null)
              setFollowUpOpen(true)
            }}
          >
            + Add Follow-up
          </Button>
        </div>
        {followUps.length === 0 ? (
          <p className='text-muted-foreground text-sm'>No follow-ups yet.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Follow-up</TableHead>
                <TableHead>Assigned To</TableHead>
                <TableHead>Due</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {followUps.map(item => (
                <TableRow key={item.id}>
                  <TableCell className='font-medium'>{item.title}</TableCell>
                  <TableCell>{item.assigned_to?.display_name || item.assigned_to?.name || 'Unassigned'}</TableCell>
                  <TableCell>{formatDueAt(item.due_at) || '—'}</TableCell>
                  <TableCell className={followUpStatusClass(item.status)}>{item.status_label}</TableCell>
                  <TableCell>
                    <div className='flex flex-wrap gap-1'>
                      {item.status !== 'completed' && item.status !== 'cancelled' && (
                        <Button type='button' size='sm' variant='outline' disabled={!canChange} onClick={() => void completeFollowUp(item)}>
                          Complete
                        </Button>
                      )}
                      <Button
                        type='button'
                        size='sm'
                        variant='ghost'
                        disabled={!canChange}
                        onClick={() => {
                          setEditingFollowUp(item)
                          setFollowUpOpen(true)
                        }}
                      >
                        Edit
                      </Button>
                      {item.status !== 'cancelled' && item.status !== 'completed' && (
                        <Button type='button' size='sm' variant='ghost' disabled={!canChange} onClick={() => void cancelFollowUp(item)}>
                          Cancel
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>

      <CasePaymentsSection opportunity={opportunity} />

      <section className='bg-card rounded-xl border p-5'>
        <h2 className='text-sm font-semibold tracking-wide uppercase'>Conversation / request history</h2>
        {messages.length === 0 ? (
          <p className='text-muted-foreground mt-2 text-sm'>
            {opportunity.conversation
              ? 'This conversation has no stored messages yet.'
              : 'No originating conversation is linked to this case.'}
          </p>
        ) : (
          <ol className='mt-3 space-y-3'>
            {messages.map(message => (
              <li key={message.id} className='rounded-md border px-3 py-2'>
                <p className='text-xs font-medium'>{senderLabel(message.sender_type)}</p>
                <p className='mt-1 text-sm whitespace-pre-wrap'>{message.content}</p>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section className='bg-card rounded-xl border p-5'>
        <h2 className='text-sm font-semibold tracking-wide uppercase'>Activity</h2>
        {activities.length === 0 ? (
          <p className='text-muted-foreground mt-2 text-sm'>No case activity recorded yet.</p>
        ) : (
          <ol className='mt-3 space-y-3'>
            {activities.map(item => (
              <li key={item.id} className='border-b pb-3 last:border-0 last:pb-0'>
                <p className='text-muted-foreground text-xs'>{formatRelativeTime(item.created_at)}</p>
                <p className='text-sm'>{item.message}</p>
              </li>
            ))}
          </ol>
        )}
      </section>

      <CustomerDetailSheet
        customer={customerOpen ? customerFromOpportunity(opportunity) : null}
        onOpenChange={open => setCustomerOpen(open)}
      />
      <QuoteOpportunityDialog
        opportunity={quoteOpen ? opportunity : null}
        onOpenChange={setQuoteOpen}
        onQuoted={updated => setOpportunity(updated)}
      />
      <TransferOpportunityDialog
        opportunity={transferOpen ? opportunity : null}
        canViewUsers={canViewUsers}
        onOpenChange={setTransferOpen}
        onTransferred={updated => setOpportunity(updated)}
      />
      <OpportunityHistorySheet opportunity={historyOpen ? opportunity : null} onOpenChange={setHistoryOpen} />
      <AddOpportunityNoteDialog
        opportunity={noteOpen ? opportunity : null}
        user={user}
        onOpenChange={setNoteOpen}
        onSaved={updated => setOpportunity(updated)}
      />
      <CaseFollowUpDialog
        key={followUpOpen ? `${opportunity.id}-${editingFollowUp?.id ?? 'new'}` : 'closed'}
        caseRecord={followUpOpen ? opportunity : null}
        followUp={editingFollowUp}
        canViewUsers={canViewUsers}
        onOpenChange={open => {
          setFollowUpOpen(open)
          if (!open) setEditingFollowUp(null)
        }}
        onSaved={updated => {
          if (updated) setOpportunity(updated)
        }}
      />
    </div>
  )
}

export default OpportunityDetailView
