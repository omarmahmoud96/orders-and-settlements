/** Shapes returned by the Django API. Every monetary value is a `string` on purpose. */

export type OrderStatus = 'pending' | 'partially_paid' | 'paid' | 'overdue';

export const ORDER_STATUSES: OrderStatus[] = [
  'pending',
  'partially_paid',
  'paid',
  'overdue',
];

export const STATUS_LABELS: Record<OrderStatus, string> = {
  pending: 'Pending',
  partially_paid: 'Partially paid',
  paid: 'Paid',
  overdue: 'Overdue',
};

export interface User {
  id: number;
  email: string;
  name: string;
  date_joined: string;
}

export interface LineItem {
  id: number;
  description: string;
  quantity: number;
  unit_price: string;
  line_total: string;
}

export interface Payment {
  id: number;
  amount: string;
  paid_on: string;
  note: string;
  created_at: string;
}

export interface Refund {
  id: number;
  amount: string;
  refunded_on: string;
  reason: string;
  refunded_payment: number | null;
  created_at: string;
}

export interface AuditEntry {
  id: number;
  event:
    | 'order_created'
    | 'order_updated'
    | 'payment_recorded'
    | 'refund_issued'
    | 'status_changed';
  status_from: string;
  status_to: string;
  metadata: Record<string, unknown>;
  actor_email: string | null;
  created_at: string;
}

export interface OrderSummary {
  id: number;
  customer: string;
  due_date: string;
  total: string;
  amount_paid: string;
  amount_due: string;
  status: OrderStatus;
  created_at: string;
  updated_at: string;
}

export interface OrderDetail extends OrderSummary {
  is_locked: boolean;
  editable_fields: string[];
  line_items: LineItem[];
  payments: Payment[];
  refunds: Refund[];
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface StatusBucket {
  status: OrderStatus;
  count: number;
  total: string;
  amount_due: string;
}

export interface DashboardSummary {
  order_count: number;
  total: string;
  amount_paid: string;
  amount_due: string;
  by_status: StatusBucket[];
}
