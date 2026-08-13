/**
 * Route guard and proactive token refresh.
 *
 * This is Next.js Proxy -- what was called Middleware before Next 16. The file
 * must be named `proxy.ts` and export `proxy`; the old `middleware` name is not
 * picked up. It runs on the Node runtime, which is not configurable.
 */

import { type NextRequest, NextResponse } from 'next/server';

import { API_BASE_URL } from '@/lib/env';
import { ACCESS_COOKIE, REFRESH_COOKIE, isExpiring } from '@/lib/tokens';

const PUBLIC_PATHS = ['/login', '/register'];

const COOKIE_OPTIONS = {
  httpOnly: true,
  sameSite: 'lax' as const,
  secure: process.env.NODE_ENV === 'production',
  path: '/',
};

export async function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const isPublic = PUBLIC_PATHS.some((path) => pathname.startsWith(path));

  const access = request.cookies.get(ACCESS_COOKIE)?.value;
  const refresh = request.cookies.get(REFRESH_COOKIE)?.value;

  if (!refresh) {
    if (isPublic) return NextResponse.next();
    const login = new URL('/login', request.url);
    if (pathname !== '/')
      login.searchParams.set('next', `${pathname}${search}`);
    const response = NextResponse.redirect(login);
    response.cookies.delete(ACCESS_COOKIE);
    return response;
  }

  if (isPublic) {
    return NextResponse.redirect(new URL('/', request.url));
  }

  if (!isExpiring(access)) {
    return NextResponse.next();
  }

  try {
    const refreshed = await fetch(`${API_BASE_URL}/api/auth/refresh/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh }),
      cache: 'no-store',
    });

    if (!refreshed.ok) {
      const response = NextResponse.redirect(new URL('/login', request.url));
      response.cookies.delete(ACCESS_COOKIE);
      response.cookies.delete(REFRESH_COOKIE);
      return response;
    }

    const tokens = (await refreshed.json()) as {
      access: string;
      refresh?: string;
    };

    // Hand the new token to this request too, so the page render that follows
    // does not have to wait for the next navigation to see it.
    const headers = new Headers(request.headers);
    const response = NextResponse.next({ request: { headers } });
    response.cookies.set(ACCESS_COOKIE, tokens.access, {
      ...COOKIE_OPTIONS,
      maxAge: 60 * 30,
    });
    if (tokens.refresh) {
      response.cookies.set(REFRESH_COOKIE, tokens.refresh, {
        ...COOKIE_OPTIONS,
        maxAge: 60 * 60 * 24 * 7,
      });
    }
    return response;
  } catch {
    // API unreachable: let the page render and surface a real error rather than
    // bouncing the user to a login screen that will not work either.
    return NextResponse.next();
  }
}

export const config = {
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico|.*\\.\\w+$).*)'],
};
