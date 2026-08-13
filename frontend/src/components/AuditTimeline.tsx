import { List, ListItem, Stack, Typography } from '@mui/material';

import type { AuditEntry } from '@/lib/types';

import { StatusBadge } from './StatusBadge';

const EVENT_LABELS: Record<AuditEntry['event'], string> = {
  order_created: 'Order created',
  order_updated: 'Order updated',
  payment_recorded: 'Payment recorded',
  refund_issued: 'Refund issued',
  status_changed: 'Status changed',
};

function describe(entry: AuditEntry): string | null {
  const amount = entry.metadata.amount;
  if (typeof amount === 'string') return `$${amount}`;
  const fields = entry.metadata.fields;
  if (Array.isArray(fields)) return `changed ${fields.join(', ')}`;
  const total = entry.metadata.total;
  if (typeof total === 'string') return `total $${total}`;
  return null;
}

/** Append-only history of the order (stretch goal: audit log). */
export function AuditTimeline({ entries }: { entries: AuditEntry[] }) {
  if (entries.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        Nothing recorded yet.
      </Typography>
    );
  }

  return (
    <List disablePadding>
      {entries.map((entry, index) => {
        const detail = describe(entry);
        return (
          <ListItem
            key={entry.id}
            disableGutters
            divider={index < entries.length - 1}
            sx={{ display: 'block', py: 1.25 }}>
            <Typography variant="body2">
              <Typography component="span" fontWeight={600}>
                {EVENT_LABELS[entry.event] ?? entry.event}
              </Typography>
              {detail ? (
                <Typography component="span" color="text.secondary">
                  {' '}
                  · {detail}
                </Typography>
              ) : null}
            </Typography>
            {entry.status_from && entry.status_to ? (
              <Stack
                direction="row"
                alignItems="center"
                gap={0.75}
                sx={{ mt: 0.5 }}>
                <StatusBadge status={entry.status_from} />
                <span aria-hidden="true">→</span>
                <StatusBadge status={entry.status_to} />
              </Stack>
            ) : null}
            <Typography
              variant="caption"
              color="text.secondary"
              display="block"
              sx={{ mt: 0.5 }}>
              {new Date(entry.created_at).toLocaleString('en-US', {
                dateStyle: 'medium',
                timeStyle: 'short',
              })}
              {entry.actor_email ? ` · ${entry.actor_email}` : null}
            </Typography>
          </ListItem>
        );
      })}
    </List>
  );
}
