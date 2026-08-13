import {
  Box,
  Card,
  CardContent,
  Container,
  Stack,
  Typography,
} from '@mui/material';

import { ExportForm } from '@/components/ExportForm';
import { LinkButton } from '@/components/LinkButton';
import { OrderTable } from '@/components/OrderTable';
import { SiteHeader } from '@/components/SiteHeader';
import { StatusFilter } from '@/components/StatusFilter';
import { SummaryTiles } from '@/components/SummaryTiles';
import { fetchCurrentUser, fetchOrders, fetchSummary } from '@/lib/queries';
import { ORDER_STATUSES } from '@/lib/types';

export const dynamic = 'force-dynamic';

function readStatuses(
  searchParams: Record<string, string | string[] | undefined>
): string[] {
  const raw = searchParams.status;
  const values = Array.isArray(raw) ? raw : raw ? [raw] : [];
  return values.filter((value): value is string =>
    (ORDER_STATUSES as string[]).includes(value)
  );
}

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const statuses = readStatuses(params);
  const customer =
    typeof params.customer === 'string' ? params.customer : undefined;
  const page = typeof params.page === 'string' ? params.page : undefined;

  const [user, summary, orders] = await Promise.all([
    fetchCurrentUser(),
    fetchSummary(),
    fetchOrders({ status: statuses, customer, page }),
  ]);

  return (
    <>
      <SiteHeader email={user.email} />
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Stack gap={3}>
          <Stack
            direction="row"
            gap={2}
            flexWrap="wrap"
            alignItems="flex-start">
            <Box>
              <Typography variant="h5" component="h1">
                Dashboard
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Every order you have raised, what has been paid, and what is
                still owed.
              </Typography>
            </Box>
            <Box flex={1} />
            <LinkButton href="/orders/new" variant="contained">
              New order
            </LinkButton>
          </Stack>

          <SummaryTiles summary={summary} activeStatuses={statuses} />

          <Card variant="outlined">
            <Stack
              direction="row"
              alignItems="center"
              gap={2}
              flexWrap="wrap"
              sx={{
                px: 2.5,
                py: 1.75,
                borderBottom: 1,
                borderColor: 'divider',
              }}>
              <Typography variant="h6">Orders</Typography>
              <Box flex={1} />
              <StatusFilter active={statuses} />
            </Stack>
            <OrderTable orders={orders.results} />
            {orders.count > orders.results.length ? (
              <CardContent>
                <Typography variant="body2" color="text.secondary">
                  Showing {orders.results.length} of {orders.count} orders.
                </Typography>
              </CardContent>
            ) : null}
          </Card>

          <Card variant="outlined">
            <Typography
              variant="h6"
              sx={{
                px: 2.5,
                py: 1.75,
                borderBottom: 1,
                borderColor: 'divider',
              }}>
              Export
            </Typography>
            <CardContent>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Download the orders currently in view as CSV. Leave the dates
                blank to export everything.
              </Typography>
              <ExportForm statuses={statuses} />
            </CardContent>
          </Card>
        </Stack>
      </Container>
    </>
  );
}
