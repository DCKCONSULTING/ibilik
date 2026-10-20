'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'

import { useSearchParams } from 'next/navigation'

import { isApiError } from '@/lib/api'
import type { Channel } from '@/lib/customers/types'
import { inboxApi } from '@/lib/inbox/api'
import { conversationToEmail, messageToThread } from '@/lib/inbox/map-conversation'
import type { Email, EmailLabel, EmailStatus, MailChannel, MailFilterTab, MailNavType } from '@/types/apps/mail-types'

const mergeConversationPage = (current: Email[], nextEmails: Email[], page: number) => {
  if (page === 1) return nextEmails

  return [...current, ...nextEmails.filter(item => !current.some(existing => existing.id === item.id))]
}

export const useMailApp = () => {
  const searchParams = useSearchParams()
  const requestedConversationId = searchParams.get('conversation')
  const [emails, setEmails] = useState<Email[]>([])
  const [selectedEmailId, setSelectedEmailId] = useState<string | null>(requestedConversationId)
  const [searchQuery, setSearchQuery] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [channelFilter, setChannelFilter] = useState<MailChannel | 'all'>('all')
  const [activeStatus, setActiveStatus] = useState<EmailStatus>('inbox')
  const [activeLabel, setActiveLabel] = useState<EmailLabel | null>(null)
  const [activeNavType, setActiveNavType] = useState<MailNavType>('status')
  const [filterTab, setFilterTab] = useState<MailFilterTab>('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [sending, setSending] = useState(false)
  const [messagePage, setMessagePage] = useState(1)
  const [hasMoreMessages, setHasMoreMessages] = useState(false)
  const [conversationPage, setConversationPage] = useState(1)
  const [hasMoreConversations, setHasMoreConversations] = useState(false)

  useEffect(() => {
    const handle = window.setTimeout(() => setDebouncedSearch(searchQuery.trim()), 300)

    return () => window.clearTimeout(handle)
  }, [searchQuery])

  const loadConversations = useCallback(async (page = 1) => {
    return inboxApi.listConversations({
      search: debouncedSearch || undefined,
      channel: channelFilter === 'all' ? undefined : channelFilter,
      unread: filterTab === 'unread' ? true : undefined,
      page,
      page_size: 30
    })
  }, [channelFilter, debouncedSearch, filterTab])

  useEffect(() => {
    let mounted = true

    loadConversations(1)
      .then(payload => {
        if (!mounted) return

        const results = Array.isArray(payload.results) ? payload.results : []

        setEmails(results.map(item => conversationToEmail(item)))
        setHasMoreConversations(Boolean(payload.has_next))
        setConversationPage(1)
        setError(null)
      })
      .catch(err => {
        if (!mounted) return

        setError(isApiError(err) ? err.message : 'Unable to load conversations.')
        setEmails([])
      })
      .finally(() => {
        if (!mounted) return

        setLoading(false)
      })

    return () => {
      mounted = false
    }
  }, [loadConversations])

  useEffect(() => {
    const conversationId = Number(requestedConversationId)

    if (!Number.isInteger(conversationId) || conversationId <= 0) return

    let mounted = true

    inboxApi
      .getConversation(conversationId)
      .then(conversation => {
        if (!mounted) return

        const email = conversationToEmail(conversation)

        setEmails(current => (current.some(item => item.id === email.id) ? current : [email, ...current]))
        setSelectedEmailId(email.id)
      })
      .catch(() => undefined)

    return () => {
      mounted = false
    }
  }, [requestedConversationId])

  const visibleEmails = emails

  const selectedEmail = useMemo(() => {
    if (selectedEmailId) {
      const selected = emails.find(email => email.id === selectedEmailId)

      if (selected) return selected
    }

    return visibleEmails[0] ?? null
  }, [emails, selectedEmailId, visibleEmails])

  const selectedConversationId = selectedEmail?.conversationId ?? null

  useEffect(() => {
    if (!selectedConversationId) return

    let mounted = true

    inboxApi
      .listMessages(selectedConversationId, { page: 1, page_size: 50 })
      .then(payload => {
        if (!mounted) return

        const thread = payload.results.map(messageToThread)

        setEmails(current =>
          current.map(email => {
            if (email.conversationId !== selectedConversationId) return email

            return {
              ...email,
              isRead: true,
              hasMoreMessages: payload.has_next,
              thread: { messages: thread }
            }
          })
        )
        setMessagePage(1)
        setHasMoreMessages(payload.has_next)
      })
      .catch(err => {
        if (!mounted) return

        setError(isApiError(err) ? err.message : 'Unable to load messages.')
      })

    return () => {
      mounted = false
    }
  }, [selectedConversationId])

  const unreadCount = useMemo(() => emails.filter(email => !email.isRead).length, [emails])

  const handleStatusChange = useCallback((status: EmailStatus) => {
    setActiveNavType('status')
    setActiveStatus(status)
    setActiveLabel(null)
    setSelectedEmailId(null)
  }, [])

  const handleLabelChange = useCallback((label: EmailLabel) => {
    setActiveNavType('label')
    setActiveLabel(label)
    setSelectedEmailId(null)
  }, [])

  const handleEmailSelect = useCallback((email: Email) => {
    setSelectedEmailId(email.id)
  }, [])

  const reloadConversations = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const payload = await loadConversations(1)
      const results = Array.isArray(payload.results) ? payload.results : []

      setEmails(results.map(item => conversationToEmail(item)))
      setHasMoreConversations(Boolean(payload.has_next))
      setConversationPage(1)
    } catch (err) {
      setError(isApiError(err) ? err.message : 'Unable to load conversations.')
      setEmails([])
    } finally {
      setLoading(false)
    }
  }, [loadConversations])

  const loadMoreConversations = useCallback(async () => {
    const page = conversationPage + 1

    const payload = await loadConversations(page)

    const nextEmails = payload.results.map(item => conversationToEmail(item))

    setEmails(current => mergeConversationPage(current, nextEmails, page))

    setHasMoreConversations(payload.has_next)
    setConversationPage(page)
  }, [conversationPage, loadConversations])

  const loadEarlierMessages = useCallback(async () => {
    if (!selectedConversationId || !hasMoreMessages) return

    const page = messagePage + 1

    const payload = await inboxApi.listMessages(selectedConversationId, { page, page_size: 50 })

    const thread = payload.results.map(messageToThread)

    setEmails(current =>
      current.map(email => {
        if (email.conversationId !== selectedConversationId) return email

        return {
          ...email,
          hasMoreMessages: payload.has_next,
          thread: { messages: [...thread, ...email.thread.messages] }
        }
      })
    )

    setMessagePage(page)
    setHasMoreMessages(payload.has_next)
  }, [hasMoreMessages, messagePage, selectedConversationId])

  const sendReply = useCallback(async (content: string, channel: Channel) => {
    if (!selectedConversationId) {
      throw new Error('No conversation selected.')
    }

    setSending(true)

    try {
      const message = await inboxApi.sendMessage(selectedConversationId, { content, channel })
      const threadMessage = messageToThread(message)

      setEmails(current =>
        current.map(email => {
          if (email.conversationId !== selectedConversationId) return email

          return {
            ...email,
            preview: message.content,
            body: message.content,
            date: threadMessage.date,
            thread: { messages: [...email.thread.messages, threadMessage] }
          }
        })
      )

      return message
    } catch (err) {
      throw new Error(isApiError(err) ? err.message : 'Unable to send message. Please try again.')
    } finally {
      setSending(false)
    }
  }, [selectedConversationId])

  return {
    activeStatus,
    activeLabel,
    activeNavType,
    filterTab,
    searchQuery,
    channelFilter,
    statusCounts: {
      inbox: emails.length,
      sent: 0,
      drafts: 0,
      spam: 0,
      trash: 0,
      archive: 0
    },
    labelCounts: {
      social: 0,
      updates: 0,
      forums: 0,
      shopping: 0,
      promotions: 0
    },
    visibleEmails,
    selectedEmail,
    unreadCount,
    loading,
    error,
    sending,
    hasMoreMessages,
    hasMoreConversations,
    setFilterTab,
    reloadConversations,
    setSearchQuery,
    setChannelFilter,
    handleStatusChange,
    handleLabelChange,
    handleEmailSelect,
    loadEarlierMessages,
    loadMoreConversations,
    sendReply
  }
}
