import { Chip, type ChipProps } from '@mui/material';

import { type OrderStatus, STATUS_LABELS } from '@/lib/types';

const STATUS_COLOR: Record<OrderStatus, ChipProps['color']> = {
  pending: 'default',
  partially_paid: 'warning',
  paid: 'success',
  overdue: 'error',
};

export function StatusBadge({ status }: { status: string }) {
  const known = status in STATUS_LABELS;
  return (
    <Chip
      size="small"
      label={known ? STATUS_LABELS[status as OrderStatus] : status}
      color={known ? STATUS_COLOR[status as OrderStatus] : 'default'}
      variant={known && status === 'overdue' ? 'outlined' : 'filled'}
    />
  );
}
