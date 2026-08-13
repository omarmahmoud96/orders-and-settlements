/**
 * Server-side environment configuration, validated at import time.
 *
 * Kept free of `next/headers` and `server-only` so that `proxy.ts` (which runs
 * before a request has a cookie jar it can await) can import it too.
 */

function required(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`${name} is required. See .env.example.`);
  }
  return value.replace(/\/$/, '');
}

export const API_BASE_URL = required('API_BASE_URL');
