'use client';

import { Chip, Stack } from '@mui/material';
import Link from 'next/link';

import { ORDER_STATUSES, STATUS_LABELS } from '@/lib/types';

/**
 * Status filter as links rather than client-side state, so the current filter
 * lives in the URL: it survives a refresh, can be bookmarked, and is applied by
 * the database rather than by hiding rows after the fact.
 */
export function StatusFilter({ active }: { active: string[] }) {
  return (
    <Stack
      direction="row"
      gap={1}
      flexWrap="wrap"
      component="nav"
      aria-label="Filter orders by status">
      <Chip
        component={Link}
        href="/"
        clickable
        label="All"
        variant={active.length === 0 ? 'filled' : 'outlined'}
        color={active.length === 0 ? 'primary' : 'default'}
      />
      {ORDER_STATUSES.map((status) => {
        const isActive = active.includes(status);
        return (
          <Chip
            key={status}
            component={Link}
            href={`/?status=${status}`}
            clickable
            label={STATUS_LABELS[status]}
            variant={isActive ? 'filled' : 'outlined'}
            color={isActive ? 'primary' : 'default'}
          />
        );
      })}
    </Stack>
  );
}
