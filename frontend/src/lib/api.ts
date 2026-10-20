import { env } from '@/lib/env'

export const DEFAULT_API_TIMEOUT_MS = 15_000

export type QueryValue = string | number | boolean | null | undefined

export type ApiRequestOptions = {
  headers?: HeadersInit
  query?: Record<string, QueryValue>
  cache?: RequestCache
  signal?: AbortSignal
  timeoutMs?: number
  skipCsrf?: boolean
}

export type ApiErrorBody = {
  message?: unknown
  error?: unknown
  code?: unknown
  requestId?: unknown
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string | undefined
  readonly requestId: string | undefined

  constructor(params: { message: string; status: number; code?: string; requestId?: string }) {
    super(params.message)
    this.name = 'ApiError'
    this.status = params.status
    this.code = params.code
    this.requestId = params.requestId
  }
}

export const isApiError = (value: unknown): value is ApiError => value instanceof ApiError

const isAbsoluteUrl = (path: string) => path.startsWith('http://') || path.startsWith('https://')

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const asOptionalString = (value: unknown): string | undefined => {
  if (typeof value !== 'string') return undefined

  const trimmed = value.trim()

  return trimmed.length > 0 ? trimmed : undefined
}

const resolveUrl = (path: string, query?: Record<string, QueryValue>): string => {
  const baseUrl = isAbsoluteUrl(path) ? path : `${env.apiBaseUrl}${path.startsWith('/') ? path : `/${path}`}`
  const url = new URL(baseUrl, env.apiBaseUrl || env.appUrl)

  if (query) {
    Object.entries(query).forEach(([key, value]) => {
      if (value === undefined || value === null) return

      url.searchParams.set(key, String(value))
    })
  }

  if (isAbsoluteUrl(path) || env.apiBaseUrl) {
    return url.toString()
  }

  return `${url.pathname}${url.search}`
}

const CSRF_COOKIE_NAME = 'csrftoken'
const CSRF_HEADER_NAME = 'X-CSRFToken'

const readCookie = (name: string): string | undefined => {
  if (typeof document === 'undefined') return undefined

  const cookies = document.cookie.split(';')

  for (const cookie of cookies) {
    const [rawName, ...rawValue] = cookie.split('=')

    if (rawName.trim() === name) {
      return decodeURIComponent(rawValue.join('='))
    }
  }

  return undefined
}

let csrfTokenPromise: Promise<string | undefined> | null = null

const isUnsafeMethod = (method: string) => !['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(method)

const fetchCsrfToken = async (): Promise<string | undefined> => {
  const response = await fetch(resolveUrl('/api/auth/csrf/'), {
    method: 'GET',
    headers: { Accept: 'application/json' },
    credentials: 'include',
    cache: 'no-store'
  })

  if (!response.ok) return readCookie(CSRF_COOKIE_NAME)

  try {
    const payload = (await response.json()) as { csrfToken?: unknown }

    return asOptionalString(payload.csrfToken) ?? readCookie(CSRF_COOKIE_NAME)
  } catch {
    return readCookie(CSRF_COOKIE_NAME)
  }
}

const ensureCsrfToken = async (): Promise<string | undefined> => {
  const existing = readCookie(CSRF_COOKIE_NAME)

  if (existing) return existing
  if (csrfTokenPromise) return csrfTokenPromise

  csrfTokenPromise = fetchCsrfToken().finally(() => {
    csrfTokenPromise = null
  })

  return csrfTokenPromise
}

const defaultMessageForStatus = (status: number): string => {
  if (status === 0) return 'Unable to reach the server. Please try again.'
  if (status === 401) return 'Session expired. Please sign in again.'
  if (status === 403) return 'You do not have permission to perform this action.'
  if (status === 404) return 'The requested resource was not found.'
  if (status === 408) return 'The request timed out. Please try again.'
  if (status === 422) return 'The request could not be validated.'
  if (status >= 500) return 'A server error occurred. Please try again later.'

  return 'The request failed. Please try again.'
}

const readErrorPayload = async (response: Response): Promise<ApiErrorBody | undefined> => {
  const contentType = response.headers.get('content-type') ?? ''

  if (!contentType.includes('application/json')) return undefined

  try {
    const payload = (await response.json()) as unknown

    return isRecord(payload) ? payload : undefined
  } catch {
    return undefined
  }
}

const toApiError = async (response: Response): Promise<ApiError> => {
  const payload = await readErrorPayload(response)
  const requestId = asOptionalString(payload?.requestId) ?? asOptionalString(response.headers.get('x-request-id'))
  const message = asOptionalString(payload?.message) ?? asOptionalString(payload?.error) ?? defaultMessageForStatus(response.status)

  return new ApiError({
    message,
    status: response.status,
    code: asOptionalString(payload?.code),
    requestId
  })
}

const parseSuccessBody = async <T>(response: Response): Promise<T> => {
  if (response.status === 204) {
    return undefined as T
  }

  const contentType = response.headers.get('content-type') ?? ''
  const rawBody = await response.text()

  if (!rawBody) {
    return undefined as T
  }

  if (contentType.includes('application/json')) {
    return JSON.parse(rawBody) as T
  }

  return rawBody as T
}

const buildHeaders = (body: unknown, headers?: HeadersInit): Headers => {
  const nextHeaders = new Headers(headers)

  if (!nextHeaders.has('Accept')) {
    nextHeaders.set('Accept', 'application/json')
  }

  const isJsonBody = body !== undefined && !(body instanceof FormData) && !(body instanceof Blob)

  if (isJsonBody && !nextHeaders.has('Content-Type')) {
    nextHeaders.set('Content-Type', 'application/json')
  }

  return nextHeaders
}

const serializeBody = (body: unknown): BodyInit | undefined => {
  if (body === undefined) return undefined
  if (body instanceof FormData || body instanceof Blob || typeof body === 'string') return body

  return JSON.stringify(body)
}

const request = async <T>(
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE',
  path: string,
  body?: unknown,
  options: ApiRequestOptions = {}
): Promise<T> => {
  const timeoutMs = options.timeoutMs ?? DEFAULT_API_TIMEOUT_MS
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

  const abortFromCaller = () => controller.abort()

  options.signal?.addEventListener('abort', abortFromCaller)

  try {
    const headers = buildHeaders(body, options.headers)

    if (isUnsafeMethod(method) && !options.skipCsrf && !headers.has(CSRF_HEADER_NAME)) {
      const csrfToken = await ensureCsrfToken()

      if (csrfToken) {
        headers.set(CSRF_HEADER_NAME, csrfToken)
      }
    }

    const response = await fetch(resolveUrl(path, options.query), {
      method,
      headers,
      body: serializeBody(body),
      credentials: 'include',
      cache: options.cache,
      signal: controller.signal
    })

    if (!response.ok) {
      throw await toApiError(response)
    }

    return await parseSuccessBody<T>(response)
  } catch (error) {
    if (isApiError(error)) {
      throw error
    }

    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiError({
        message: defaultMessageForStatus(408),
        status: 408,
        code: 'TIMEOUT'
      })
    }

    throw new ApiError({
      message: defaultMessageForStatus(0),
      status: 0,
      code: 'NETWORK'
    })
  } finally {
    clearTimeout(timeoutId)
    options.signal?.removeEventListener('abort', abortFromCaller)
  }
}

const filenameFromDisposition = (header: string | null, fallback: string) => {
  if (!header) return fallback

  const utfMatch = header.match(/filename\*=UTF-8''([^;]+)/i)
  if (utfMatch?.[1]) return decodeURIComponent(utfMatch[1])

  const match = header.match(/filename="?([^"]+)"?/i)
  return match?.[1] ?? fallback
}

const download = async (path: string, fallbackName: string, options: ApiRequestOptions = {}) => {
  const timeoutMs = options.timeoutMs ?? DEFAULT_API_TIMEOUT_MS
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

  try {
    const headers = buildHeaders(undefined, options.headers)
    headers.set('Accept', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    const response = await fetch(resolveUrl(path, options.query), {
      method: 'GET',
      headers,
      credentials: 'include',
      cache: 'no-store',
      signal: controller.signal
    })

    if (!response.ok) {
      throw await toApiError(response)
    }

    const blob = await response.blob()
    const filename = filenameFromDisposition(response.headers.get('content-disposition'), fallbackName)
    const objectUrl = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = objectUrl
    link.download = filename
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(objectUrl)

    return filename
  } catch (error) {
    if (isApiError(error)) throw error
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiError({ message: defaultMessageForStatus(408), status: 408, code: 'TIMEOUT' })
    }
    throw new ApiError({ message: defaultMessageForStatus(0), status: 0, code: 'NETWORK' })
  } finally {
    clearTimeout(timeoutId)
  }
}

export const api = {
  get<T>(path: string, options?: ApiRequestOptions) {
    return request<T>('GET', path, undefined, options)
  },
  post<T>(path: string, body?: unknown, options?: ApiRequestOptions) {
    return request<T>('POST', path, body, options)
  },
  put<T>(path: string, body?: unknown, options?: ApiRequestOptions) {
    return request<T>('PUT', path, body, options)
  },
  patch<T>(path: string, body?: unknown, options?: ApiRequestOptions) {
    return request<T>('PATCH', path, body, options)
  },
  delete<T>(path: string, options?: ApiRequestOptions) {
    return request<T>('DELETE', path, undefined, options)
  },
  download
}
