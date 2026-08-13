/** Read-side API calls used by Server Components. */

import 'server-only';

import { apiRequest, queryString } from './api';
import type {
  AuditEntry,
  DashboardSummary,
  OrderDetail,
  OrderSummary,
  Paginated,
  User,
} from './types';

export async function fetchCurrentUser(): Promise<User> {
  return apiRequest<User>('/api/auth/me/');
}

export async function fetchSummary(): Promise<DashboardSummary> {
  return apiRequest<DashboardSummary>('/api/summary/');
}

export interface OrderListParams {
  status?: string[];
  customer?: string;
  ordering?: string;
  page?: string;
}

export async function fetchOrders(
  params: OrderListParams = {}
): Promise<Paginated<OrderSummary>> {
  return apiRequest<Paginated<OrderSummary>>(
    `/api/orders/${queryString({
      status: params.status,
      customer: params.customer,
      ordering: params.ordering,
      page: params.page,
    })}`
  );
}

export async function fetchOrder(id: string): Promise<OrderDetail> {
  return apiRequest<OrderDetail>(`/api/orders/${id}/`);
}

export async function fetchAuditLog(id: string): Promise<AuditEntry[]> {
  const page = await apiRequest<Paginated<AuditEntry>>(
    `/api/orders/${id}/audit-log/`
  );
  return page.results;
}
