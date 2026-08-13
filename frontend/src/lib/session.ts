/** Token custody: cookie read/write helpers. */

import { cookies } from 'next/headers';

import { ACCESS_COOKIE, REFRESH_COOKIE } from './tokens';

export { ACCESS_COOKIE, REFRESH_COOKIE, isExpiring, jwtExpiry } from './tokens';

const BASE_OPTIONS = {
  httpOnly: true,
  sameSite: 'lax' as const,
  secure: process.env.NODE_ENV === 'production',
  path: '/',
};

export async function getAccessToken(): Promise<string | undefined> {
  return (await cookies()).get(ACCESS_COOKIE)?.value;
}

export async function getRefreshToken(): Promise<string | undefined> {
  return (await cookies()).get(REFRESH_COOKIE)?.value;
}

/**
 * Persist a token pair.
 *
 * Only a Server Action or Route Handler may write cookies; during a Server
 * Component render the write is not possible, so it is skipped.
 */
export async function setTokens(
  access: string,
  refresh?: string
): Promise<void> {
  try {
    const jar = await cookies();
    jar.set(ACCESS_COOKIE, access, { ...BASE_OPTIONS, maxAge: 60 * 30 });
    if (refresh) {
      jar.set(REFRESH_COOKIE, refresh, {
        ...BASE_OPTIONS,
        maxAge: 60 * 60 * 24 * 7,
      });
    }
  } catch {
    // Read-only cookie context (Server Component render). Not fatal.
  }
}

export async function clearTokens(): Promise<void> {
  try {
    const jar = await cookies();
    jar.delete(ACCESS_COOKIE);
    jar.delete(REFRESH_COOKIE);
  } catch {
    // As above.
  }
}
