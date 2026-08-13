/**
 * Cookie names and JWT inspection.
 *
 * Kept free of `next/headers` so that middleware (which runs before a request
 * has a cookie jar it can await) can import it too.
 */

export const ACCESS_COOKIE = 'os_access';
export const REFRESH_COOKIE = 'os_refresh';

/** Seconds-since-epoch expiry claim of a JWT, without verifying the signature. */
export function jwtExpiry(token: string): number | null {
  const payload = token.split('.')[1];
  if (!payload) return null;
  try {
    const normalised = payload.replace(/-/g, '+').replace(/_/g, '/');
    const decoded = JSON.parse(atob(normalised)) as { exp?: number };
    return typeof decoded.exp === 'number' ? decoded.exp : null;
  } catch {
    return null;
  }
}

/** True when the token is missing, unreadable, or within `skewSeconds` of expiry. */
export function isExpiring(
  token: string | undefined,
  skewSeconds = 60
): boolean {
  if (!token) return true;
  const exp = jwtExpiry(token);
  if (exp === null) return true;
  return exp - skewSeconds <= Math.floor(Date.now() / 1000);
}
