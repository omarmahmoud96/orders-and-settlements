import {
  Box,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import Link from 'next/link';

import { formatMoney } from '@/lib/money';
import type { OrderSummary } from '@/lib/types';

import { StatusBadge } from './StatusBadge';

function formatDate(value: string): string {
  return new Date(`${value}T00:00:00`).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

function daysFromToday(dueDate: string): number {
  const due = new Date(`${dueDate}T00:00:00`);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((due.getTime() - today.getTime()) / 86_400_000);
}

function DueDate({ order }: { order: OrderSummary }) {
  const days = daysFromToday(order.due_date);
  const settled = order.status === 'paid';

  let note = '';
  if (!settled && days < 0) note = `${Math.abs(days)}d overdue`;
  else if (!settled && days === 0) note = 'due today';
  else if (!settled && days <= 7) note = `in ${days}d`;

  return (
    <>
      {formatDate(order.due_date)}
      {note ? (
        <Typography
          component="span"
          variant="caption"
          color="text.secondary"
          sx={{ ml: 1 }}>
          {note}
        </Typography>
      ) : null}
    </>
  );
}

export function OrderTable({ orders }: { orders: OrderSummary[] }) {
  if (orders.length === 0) {
    return (
      <Typography color="text.secondary" sx={{ p: 5, textAlign: 'center' }}>
        No orders match this filter. <Link href="/orders/new">Create one</Link>.
      </Typography>
    );
  }

  return (
    <TableContainer sx={{ overflowX: 'auto' }}>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>#</TableCell>
            <TableCell>Customer</TableCell>
            <TableCell>Status</TableCell>
            <TableCell align="right">Order total</TableCell>
            <TableCell align="right">Paid</TableCell>
            <TableCell align="right">Due</TableCell>
            <TableCell>Due date</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {orders.map((order) => (
            <TableRow
              key={order.id}
              hover
              sx={{
                position: 'relative',
                cursor: 'pointer',
                '& a.row-link::after': {
                  content: '""',
                  position: 'absolute',
                  inset: 0,
                },
              }}>
              <TableCell sx={{ color: 'text.secondary' }}>
                <Link
                  href={`/orders/${order.id}`}
                  className="row-link"
                  style={{ color: 'inherit', textDecoration: 'none' }}>
                  {order.id}
                </Link>
              </TableCell>
              <TableCell sx={{ whiteSpace: 'normal', minWidth: 200 }}>
                {order.customer}
              </TableCell>
              <TableCell>
                <StatusBadge status={order.status} />
              </TableCell>
              <TableCell
                align="right"
                sx={{ fontVariantNumeric: 'tabular-nums' }}>
                {formatMoney(order.total)}
              </TableCell>
              <TableCell
                align="right"
                sx={{ fontVariantNumeric: 'tabular-nums' }}>
                {formatMoney(order.amount_paid)}
              </TableCell>
              <TableCell
                align="right"
                sx={{ fontVariantNumeric: 'tabular-nums' }}>
                <Box component="strong">{formatMoney(order.amount_due)}</Box>
              </TableCell>
              <TableCell>
                <DueDate order={order} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
