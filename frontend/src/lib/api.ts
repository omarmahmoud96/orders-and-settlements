/** Server-side client for the Django API. */

import 'server-only';

import { API_BASE_URL } from './env';
import {
  getAccessToken,
  getRefreshToken,
  isExpiring,
  setTokens,
} from './session';

export interface ApiErrorBody {
  code: string;
  message: string;
  details: Record<string, unknown>;
}

export class ApiRequestError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.name = 'ApiRequestError';
    this.status = status;
    this.code = body.code;
    this.details = body.details ?? {};
  }

  /** Field-level messages, when the failure was a validation error. */
  get fieldErrors(): Record<string, string[]> {
    const fields = this.details.fields;
    return (fields as Record<string, string[]>) ?? {};
  }
}

async function parseError(response: Response): Promise<ApiErrorBody> {
  try {
    const body = (await response.json()) as { error?: ApiErrorBody };
    if (body?.error?.message) return body.error;
  } catch {
    // fall through to the generic message below
  }
  return {
    code: 'UNEXPECTED',
    message: `The server returned an unexpected ${response.status} response.`,
    details: {},
  };
}

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown;
  /** Skip the Authorization header (login, register, refresh). */
  anonymous?: boolean;
}

async function refreshAccessToken(): Promise<string | null> {
  const refresh = await getRefreshToken();
  if (!refresh) return null;

  const response = await fetch(`${API_BASE_URL}/api/auth/refresh/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh }),
    cache: 'no-store',
  });
  if (!response.ok) return null;

  const body = (await response.json()) as { access: string; refresh?: string };
  await setTokens(body.access, body.refresh);
  return body.access;
}

async function send(
  path: string,
  options: RequestOptions,
  token: string | undefined
): Promise<Response> {
  const { body, anonymous, headers, ...rest } = options;
  return fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers: {
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...(token && !anonymous ? { Authorization: `Bearer ${token}` } : {}),
      ...(headers as Record<string, string> | undefined),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    cache: 'no-store',
  });
}

/** Perform a request, refreshing the access token once if it has expired. */
export async function apiFetch(
  path: string,
  options: RequestOptions = {}
): Promise<Response> {
  let token = options.anonymous ? undefined : await getAccessToken();

  if (!options.anonymous && isExpiring(token)) {
    token = (await refreshAccessToken()) ?? token;
  }

  let response = await send(path, options, token);

  if (response.status === 401 && !options.anonymous) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      response = await send(path, options, refreshed);
    }
  }

  return response;
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const response = await apiFetch(path, options);

  if (!response.ok) {
    throw new ApiRequestError(response.status, await parseError(response));
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

/** Build a query string, dropping empty values and expanding arrays. */
export function queryString(
  params: Record<string, string | string[] | undefined | null>
): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue;
    for (const item of Array.isArray(value) ? value : [value]) {
      if (item !== '') search.append(key, item);
    }
  }
  const encoded = search.toString();
  return encoded ? `?${encoded}` : '';
}
