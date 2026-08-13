'use client';

import {
  Card,
  CardActionArea,
  CardContent,
  Grid,
  Typography,
} from '@mui/material';
import Link from 'next/link';

import { formatMoney } from '@/lib/money';
import { type DashboardSummary, STATUS_LABELS } from '@/lib/types';

function Tile({
  label,
  value,
  meta,
  href,
  active,
}: {
  label: string;
  value: string;
  meta: string;
  href?: string;
  active?: boolean;
}) {
  const content = (
    <CardContent>
      <Typography
        variant="overline"
        color="text.secondary"
        sx={{ letterSpacing: 0.6 }}>
        {label}
      </Typography>
      <Typography variant="h5" sx={{ fontVariantNumeric: 'tabular-nums' }}>
        {value}
      </Typography>
      <Typography variant="caption" color="text.secondary">
        {meta}
      </Typography>
    </CardContent>
  );

  return (
    <Grid size={{ xs: 12, sm: 6, md: 3 }}>
      <Card
        variant="outlined"
        sx={
          active ? { borderColor: 'primary.main', borderWidth: 2 } : undefined
        }>
        {href ? (
          <CardActionArea component={Link} href={href}>
            {content}
          </CardActionArea>
        ) : (
          content
        )}
      </Card>
    </Grid>
  );
}

/**
 * Dashboard tiles. Each status tile is a link that applies its own filter, so
 * "$4,000 overdue" is one click away from the list of which orders those are.
 */
export function SummaryTiles({
  summary,
  activeStatuses,
}: {
  summary: DashboardSummary;
  activeStatuses: string[];
}) {
  return (
    <Grid container spacing={2}>
      <Tile
        label="Outstanding"
        value={formatMoney(summary.amount_due)}
        meta={`across ${summary.order_count} order${summary.order_count === 1 ? '' : 's'} · ${formatMoney(summary.total)} billed`}
      />
      {summary.by_status.map((bucket) => {
        const active = activeStatuses.includes(bucket.status);
        return (
          <Tile
            key={bucket.status}
            label={STATUS_LABELS[bucket.status]}
            value={String(bucket.count)}
            meta={`${formatMoney(bucket.amount_due)} due`}
            href={active ? '/' : `/?status=${bucket.status}`}
            active={active}
          />
        );
      })}
    </Grid>
  );
}
