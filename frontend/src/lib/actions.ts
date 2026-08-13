'use server';

/**
 * Server Actions -- the write side of the UI.
 *
 * Each action returns a `FormState` that `useActionState` renders, rather than
 * throwing, so a rejected payment comes back as a message next to the field
 * instead of an error page.
 */

import { revalidatePath } from 'next/cache';
import { redirect } from 'next/navigation';

import { ApiRequestError, apiRequest } from './api';
import type { FormState } from './form-state';
import { clearTokens, getRefreshToken, setTokens } from './session';
import type { OrderDetail } from './types';

function toFormState(error: unknown): FormState {
  if (error instanceof ApiRequestError) {
    const maxAllowed = error.details.max_allowed;
    return {
      error: error.message,
      code: error.code,
      fieldErrors: error.fieldErrors,
      maxAllowed: typeof maxAllowed === 'string' ? maxAllowed : undefined,
    };
  }
  return {
    error:
      'Could not reach the API. Check that the backend is running and try again.',
    code: 'NETWORK',
  };
}

function text(formData: FormData, key: string): string {
  return String(formData.get(key) ?? '').trim();
}

interface AuthResponse {
  access: string;
  refresh: string;
}

// ----------------------------------------------------------------------- auth

export async function loginAction(
  _prev: FormState,
  formData: FormData
): Promise<FormState> {
  const email = text(formData, 'email');
  const password = String(formData.get('password') ?? '');

  if (!email || !password) {
    return { error: 'Enter both your email and your password.' };
  }

  try {
    const tokens = await apiRequest<AuthResponse>('/api/auth/login/', {
      method: 'POST',
      body: { email, password },
      anonymous: true,
    });
    await setTokens(tokens.access, tokens.refresh);
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 401) {
      return {
        error: 'That email and password combination is not recognised.',
      };
    }
    return toFormState(error);
  }

  redirect('/');
}

export async function registerAction(
  _prev: FormState,
  formData: FormData
): Promise<FormState> {
  const email = text(formData, 'email');
  const name = text(formData, 'name');
  const password = String(formData.get('password') ?? '');

  if (!email || !password) {
    return { error: 'Enter an email address and a password.' };
  }

  try {
    const tokens = await apiRequest<AuthResponse>('/api/auth/register/', {
      method: 'POST',
      body: { email, name, password },
      anonymous: true,
    });
    await setTokens(tokens.access, tokens.refresh);
  } catch (error) {
    return toFormState(error);
  }

  redirect('/');
}

export async function logoutAction(): Promise<void> {
  const refresh = await getRefreshToken();
  if (refresh) {
    try {
      await apiRequest('/api/auth/logout/', {
        method: 'POST',
        body: { refresh },
      });
    } catch {
      // The local cookies are cleared regardless; a failed blacklist call must
      // not leave the user stuck in a session they asked to end.
    }
  }
  await clearTokens();
  redirect('/login');
}

// --------------------------------------------------------------------- orders

interface LineItemInput {
  description: string;
  quantity: number;
  unit_price: string;
}

function parseLineItems(formData: FormData): LineItemInput[] | null {
  try {
    const raw = String(formData.get('line_items') ?? '[]');
    const parsed = JSON.parse(raw) as LineItemInput[];
    return Array.isArray(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export async function createOrderAction(
  _prev: FormState,
  formData: FormData
): Promise<FormState> {
  const lineItems = parseLineItems(formData);
  if (!lineItems || lineItems.length === 0) {
    return { error: 'Add at least one line item before saving the order.' };
  }

  let created: OrderDetail;
  try {
    created = await apiRequest<OrderDetail>('/api/orders/', {
      method: 'POST',
      body: {
        customer: text(formData, 'customer'),
        due_date: text(formData, 'due_date'),
        line_items: lineItems,
      },
    });
  } catch (error) {
    return toFormState(error);
  }

  revalidatePath('/');
  redirect(`/orders/${created.id}`);
}

export async function updateOrderAction(
  _prev: FormState,
  formData: FormData
): Promise<FormState> {
  const id = text(formData, 'order_id');
  const body: Record<string, unknown> = {};

  const customer = text(formData, 'customer');
  const dueDate = text(formData, 'due_date');
  if (customer) body.customer = customer;
  if (dueDate) body.due_date = dueDate;

  if (Object.keys(body).length === 0) {
    return { error: 'Nothing to update.' };
  }

  try {
    await apiRequest(`/api/orders/${id}/`, { method: 'PATCH', body });
  } catch (error) {
    return toFormState(error);
  }

  revalidatePath('/');
  revalidatePath(`/orders/${id}`);
  return { ok: true, nonce: Date.now() };
}

export async function deleteOrderAction(
  _prev: FormState,
  formData: FormData
): Promise<FormState> {
  const id = text(formData, 'order_id');

  try {
    await apiRequest(`/api/orders/${id}/`, { method: 'DELETE' });
  } catch (error) {
    return toFormState(error);
  }

  revalidatePath('/');
  redirect('/');
}

// ---------------------------------------------------------------- settlements

export async function recordPaymentAction(
  _prev: FormState,
  formData: FormData
): Promise<FormState> {
  const id = text(formData, 'order_id');
  const amount = text(formData, 'amount');
  const paidOn = text(formData, 'paid_on');

  if (!amount)
    return {
      error: 'Enter the payment amount.',
      fieldErrors: { amount: ['Required'] },
    };
  if (!paidOn) return { error: 'Enter the date the payment was made.' };

  try {
    await apiRequest(`/api/orders/${id}/payments/`, {
      method: 'POST',
      body: { amount, paid_on: paidOn, note: text(formData, 'note') },
    });
  } catch (error) {
    return toFormState(error);
  }

  revalidatePath('/');
  revalidatePath(`/orders/${id}`);
  return { ok: true, nonce: Date.now() };
}

export async function recordRefundAction(
  _prev: FormState,
  formData: FormData
): Promise<FormState> {
  const id = text(formData, 'order_id');
  const amount = text(formData, 'amount');
  const refundedOn = text(formData, 'refunded_on');

  if (!amount)
    return {
      error: 'Enter the refund amount.',
      fieldErrors: { amount: ['Required'] },
    };
  if (!refundedOn) return { error: 'Enter the date of the refund.' };

  try {
    await apiRequest(`/api/orders/${id}/refunds/`, {
      method: 'POST',
      body: {
        amount,
        refunded_on: refundedOn,
        reason: text(formData, 'reason'),
      },
    });
  } catch (error) {
    return toFormState(error);
  }

  revalidatePath('/');
  revalidatePath(`/orders/${id}`);
  return { ok: true, nonce: Date.now() };
}
