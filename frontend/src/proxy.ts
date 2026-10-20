import type { NextRequest } from 'next/server'
import { NextResponse } from 'next/server'

const PUBLIC_PATHS = ['/', '/pages/auth/login', '/pages/auth/register', '/pages/auth/forgot-password']
const PUBLIC_PREFIXES = ['/pages/auth']

const isPublicPath = (pathname: string) =>
  PUBLIC_PATHS.includes(pathname) || PUBLIC_PREFIXES.some(prefix => pathname.startsWith(prefix))

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl
  const hasSession = Boolean(request.cookies.get('sessionid')?.value)

  if (pathname === '/dashboard/orders' || pathname === '/dashboard/orders/') {
    return NextResponse.redirect(new URL('/dashboard', request.url))
  }

  if (!hasSession && !isPublicPath(pathname)) {
    const loginUrl = new URL('/', request.url)

    loginUrl.searchParams.set('next', pathname)

    return NextResponse.redirect(loginUrl)
  }

  if (hasSession && pathname === '/') {
    return NextResponse.redirect(new URL('/dashboard', request.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico|images|icon.svg).*)']
}
