import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const conversationLastMessageAt = conversation =>
  conversation.last_message?.created_at || conversation.last_message_at || conversation.updated_at

const conversationLastMessagePreview = conversation =>
  conversation.last_message?.content || conversation.last_message_preview || ''

const conversationCustomerName = conversation => conversation.customer?.name?.trim() || 'Unknown customer'

const conversationToEmail = conversation => {
  const preview = conversationLastMessagePreview(conversation)

  return {
    id: String(conversation.id),
    from: conversationCustomerName(conversation),
    preview,
    date: conversationLastMessageAt(conversation),
    isRead: !conversation.is_unread,
    channel: conversation.channel
  }
}

const applySourceFilter = (conversations, channel) =>
  channel === 'all' ? conversations : conversations.filter(item => item.channel === channel)

test('conversation mapper renders API customer, preview, and latest message time', () => {
  const mapped = conversationToEmail({
    id: 123,
    channel: 'whatsapp',
    subject: '',
    last_message: {
      content: 'I need the room rate.',
      created_at: '2026-09-06T08:32:00Z'
    },
    last_message_preview: 'stale preview',
    last_message_at: '2026-09-06T07:00:00Z',
    updated_at: '2026-09-01T00:00:00Z',
    created_at: '2026-08-01T00:00:00Z',
    is_unread: true,
    customer: { id: 10, name: 'John Smith' }
  })

  assert.equal(mapped.from, 'John Smith')
  assert.equal(mapped.preview, 'I need the room rate.')
  assert.equal(mapped.date, '2026-09-06T08:32:00Z')
  assert.equal(mapped.channel, 'whatsapp')
  assert.equal(mapped.isRead, false)
})

test('conversation mapper does not drop authorized conversations without a customer name', () => {
  const mapped = conversationToEmail({
    id: 9,
    channel: 'website',
    last_message_preview: 'Hello from the website',
    last_message_at: '2026-09-06T09:00:00Z',
    is_unread: false
  })

  assert.equal(mapped.from, 'Unknown customer')
  assert.equal(mapped.preview, 'Hello from the website')
  assert.equal(mapped.date, '2026-09-06T09:00:00Z')
})

test('source filter keeps All and per-channel conversation counts', () => {
  const conversations = [
    { channel: 'website' },
    { channel: 'website' },
    { channel: 'whatsapp' },
    { channel: 'whatsapp' },
    { channel: 'whatsapp' },
    { channel: 'facebook' }
  ]

  assert.equal(applySourceFilter(conversations, 'all').length, 6)
  assert.equal(applySourceFilter(conversations, 'website').length, 2)
  assert.equal(applySourceFilter(conversations, 'whatsapp').length, 3)
  assert.equal(applySourceFilter(conversations, 'facebook').length, 1)
})

test('mail list and display no longer render archive or conversation action buttons', () => {
  const root = dirname(fileURLToPath(import.meta.url))
  const display = readFileSync(join(root, '../../views/apps/mail/mail-display/mail-display-content.tsx'), 'utf8')
  const list = readFileSync(join(root, '../../views/apps/mail/mail-list.tsx'), 'utf8')
  const item = readFileSync(join(root, '../../views/apps/mail/mail-item.tsx'), 'utf8')

  assert.equal(display.includes('hidden items-center lg:flex'), false)
  assert.equal(display.includes('Archive'), false)
  assert.equal(display.includes('Move to trash'), false)
  assert.equal(display.includes('Reply all'), false)
  assert.equal(list.includes('No conversations'), true)
  assert.equal(list.includes('Unable to load conversations.'), true)
  assert.equal(list.includes('Loading conversations...'), true)
  assert.equal(item.includes('formatRelativeTimeCompact'), true)
})
