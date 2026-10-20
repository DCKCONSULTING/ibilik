'use client'

import { useEffect, useState } from 'react'

import { PlusIcon, SearchIcon } from 'lucide-react'

import { useAuth } from '@/components/auth/auth-provider'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { InputGroup, InputGroupAddon, InputGroupInput } from '@/components/ui/input-group'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { isApiError } from '@/lib/api'
import { customersApi } from '@/lib/customers/api'
import type { Customer } from '@/lib/customers/types'
import { channelLabel, formatLastContact } from '@/lib/customers/validation'

import AddCustomerDialog from './add-customer-dialog'
import CustomerDetailSheet from './customer-detail-sheet'

const CustomersPageView = () => {
  const { can } = useAuth()
  const [customers, setCustomers] = useState<Customer[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [addOpen, setAddOpen] = useState(false)
  const [selected, setSelected] = useState<Customer | null>(null)
  const [page, setPage] = useState(1)
  const [hasNext, setHasNext] = useState(false)
  const canAdd = can('customers.add_customer')

  useEffect(() => {
    let mounted = true

    const handle = window.setTimeout(() => {
      setLoading(true)
      customersApi
        .list({ search: search.trim() || undefined, page, page_size: 20 })
        .then(payload => {
          if (!mounted) return
          setCustomers(payload.results)
          setHasNext(payload.has_next)
          setError(null)
        })
        .catch(err => {
          if (!mounted) return
          setError(isApiError(err) ? err.message : 'Unable to load customers.')
          setCustomers([])
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
  }, [page, search])

  const handleCreated = (customer: Customer) => {
    setCustomers(current => [customer, ...current.filter(item => item.id !== customer.id)])
    setSelected(customer)
  }

  return (
    <div className='flex flex-col gap-6'>
      <div className='flex flex-wrap items-center justify-between gap-3'>
        <div>
          <h1 className='text-2xl font-semibold'>Customers</h1>
          <p className='text-muted-foreground text-sm'>
            Unified customer records from website, WhatsApp, and Facebook Messenger.
          </p>
        </div>
        {canAdd && (
          <Button onClick={() => setAddOpen(true)}>
            <PlusIcon />
            Create New
          </Button>
        )}
      </div>

      {error && (
        <Alert variant='destructive'>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Card className='shadow-none'>
        <CardHeader className='gap-4'>
          <div className='flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between'>
            <div>
              <CardTitle>Customers</CardTitle>
              <CardDescription>Search and open a customer to view the full conversation history.</CardDescription>
            </div>
            <InputGroup className='sm:max-w-72'>
              <InputGroupAddon>
                <SearchIcon className='size-4' />
              </InputGroupAddon>
              <InputGroupInput
                type='search'
                placeholder='Search customers'
                value={search}
                onChange={event => {
                  setPage(1)
                  setSearch(event.target.value)
                }}
              />
            </InputGroup>
          </div>
        </CardHeader>
        <CardContent className='overflow-x-auto'>
          {loading ? (
            <p className='text-muted-foreground text-sm'>Loading customers…</p>
          ) : customers.length === 0 ? (
            <p className='text-muted-foreground text-sm'>No customers match the current filters.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Customer</TableHead>
                  <TableHead>Phone</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Properties / Interest</TableHead>
                  <TableHead>Last Contact</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {customers.map(customer => (
                  <TableRow key={customer.id} className='cursor-pointer' onClick={() => setSelected(customer)}>
                    <TableCell className='font-medium'>{customer.name}</TableCell>
                    <TableCell>{customer.phone || '—'}</TableCell>
                    <TableCell>{customer.email || '—'}</TableCell>
                    <TableCell>
                      {customer.properties.length > 0 ? customer.properties.map(item => item.name).join(', ') : '—'}
                    </TableCell>
                    <TableCell>{formatLastContact(customer.last_contact_at)}</TableCell>
                    <TableCell>
                      <div className='flex flex-wrap gap-1'>
                        {customer.sources.length === 0 ? (
                          <span className='text-muted-foreground'>—</span>
                        ) : (
                          customer.sources.map(source => (
                            <Badge key={source} variant='outline'>
                              {channelLabel(source)}
                            </Badge>
                          ))
                        )}
                      </div>
                    </TableCell>
                    <TableCell className='capitalize'>{customer.status}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          {(page > 1 || hasNext) && (
            <div className='mt-4 flex items-center justify-end gap-2'>
              <Button variant='outline' size='sm' disabled={page === 1} onClick={() => setPage(current => Math.max(1, current - 1))}>
                Previous
              </Button>
              <Button variant='outline' size='sm' disabled={!hasNext} onClick={() => setPage(current => current + 1)}>
                Next
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      <AddCustomerDialog open={addOpen} onOpenChange={setAddOpen} onCreated={handleCreated} />
      <CustomerDetailSheet
        customer={selected}
        onOpenChange={open => {
          if (!open) setSelected(null)
        }}
      />
    </div>
  )
}

export default CustomersPageView
