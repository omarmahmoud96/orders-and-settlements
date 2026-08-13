import {
  Box,
  Card,
  CardContent,
  Container,
  Grid,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableFooter,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import Link from 'next/link';
import { notFound } from 'next/navigation';

import { AuditTimeline } from '@/components/AuditTimeline';
import { OrderSettingsForm } from '@/components/OrderSettingsForm';
import { PaymentForm } from '@/components/PaymentForm';
import { RefundForm } from '@/components/RefundForm';
import { SiteHeader } from '@/components/SiteHeader';
import { StatusBadge } from '@/components/StatusBadge';
import { ApiRequestError } from '@/lib/api';
import { formatMoney } from '@/lib/money';
import { fetchAuditLog, fetchCurrentUser, fetchOrder } from '@/lib/queries';
import type { OrderDetail } from '@/lib/types';

export const dynamic = 'force-dynamic';

function formatDate(value: string): string {
  return new Date(`${value}T00:00:00`).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

function Tile({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <Grid size={{ xs: 12, sm: 6, md: 3 }}>
      <Card variant="outlined">
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
        </CardContent>
      </Card>
    </Grid>
  );
}

function Totals({ order }: { order: OrderDetail }) {
  return (
    <Grid container spacing={2}>
      <Tile label="Order total" value={formatMoney(order.total)} />
      <Tile label="Amount paid" value={formatMoney(order.amount_paid)} />
      <Tile label="Amount due" value={formatMoney(order.amount_due)} />
      <Grid size={{ xs: 12, sm: 6, md: 3 }}>
        <Card variant="outlined">
          <CardContent>
            <Typography
              variant="overline"
              color="text.secondary"
              sx={{ letterSpacing: 0.6 }}>
              Due date
            </Typography>
            <Typography variant="h6">{formatDate(order.due_date)}</Typography>
            <Box sx={{ mt: 0.5 }}>
              <StatusBadge status={order.status} />
            </Box>
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  );
}

function SectionCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <Card variant="outlined">
      <Typography
        variant="h6"
        sx={{ px: 2.5, py: 1.75, borderBottom: 1, borderColor: 'divider' }}>
        {title}
      </Typography>
      {children}
    </Card>
  );
}

export default async function OrderDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let order: OrderDetail;
  let user: Awaited<ReturnType<typeof fetchCurrentUser>>;
  try {
    [user, order] = await Promise.all([fetchCurrentUser(), fetchOrder(id)]);
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 404) notFound();
    throw error;
  }

  const auditEntries = await fetchAuditLog(id);
  const today = new Date().toISOString().slice(0, 10);

  return (
    <>
      <SiteHeader email={user.email} />
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Stack gap={3}>
          <Stack direction="row" gap={2} alignItems="flex-start">
            <Box sx={{ minWidth: 0, flex: '1 1 auto' }}>
              <Typography variant="h5" component="h1" noWrap>
                {order.customer}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                <Link href="/">Dashboard</Link> / Order #{order.id}
              </Typography>
            </Box>
            <Box sx={{ flexShrink: 0 }}>
              <StatusBadge status={order.status} />
            </Box>
          </Stack>

          <Totals order={order} />

          <Grid container spacing={3}>
            <Grid size={{ xs: 12, md: 7 }}>
              <Stack gap={3}>
                <SectionCard title="Line items">
                  <TableContainer sx={{ overflowX: 'auto' }}>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Description</TableCell>
                          <TableCell align="right">Qty</TableCell>
                          <TableCell align="right">Unit price</TableCell>
                          <TableCell align="right">Line total</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {order.line_items.map((item) => (
                          <TableRow key={item.id}>
                            <TableCell
                              sx={{ whiteSpace: 'normal', minWidth: 200 }}>
                              {item.description}
                            </TableCell>
                            <TableCell align="right">{item.quantity}</TableCell>
                            <TableCell align="right">
                              {formatMoney(item.unit_price)}
                            </TableCell>
                            <TableCell align="right">
                              {formatMoney(item.line_total)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                      <TableFooter>
                        <TableRow>
                          <TableCell colSpan={3} sx={{ fontWeight: 600 }}>
                            Subtotal
                          </TableCell>
                          <TableCell align="right" sx={{ fontWeight: 600 }}>
                            {formatMoney(order.total)}
                          </TableCell>
                        </TableRow>
                      </TableFooter>
                    </Table>
                  </TableContainer>
                </SectionCard>

                <SectionCard title="Payment history">
                  {order.payments.length === 0 ? (
                    <Typography
                      color="text.secondary"
                      sx={{ p: 5, textAlign: 'center' }}>
                      No payments recorded yet.
                    </Typography>
                  ) : (
                    <TableContainer sx={{ overflowX: 'auto' }}>
                      <Table size="small">
                        <TableHead>
                          <TableRow>
                            <TableCell>Date</TableCell>
                            <TableCell align="right">Amount</TableCell>
                            <TableCell>Note</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {order.payments.map((payment) => (
                            <TableRow key={payment.id}>
                              <TableCell>
                                {formatDate(payment.paid_on)}
                              </TableCell>
                              <TableCell align="right">
                                {formatMoney(payment.amount)}
                              </TableCell>
                              <TableCell
                                sx={{ whiteSpace: 'normal', minWidth: 200 }}>
                                {payment.note || '—'}
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                        <TableFooter>
                          <TableRow>
                            <TableCell sx={{ fontWeight: 600 }}>
                              Total received
                            </TableCell>
                            <TableCell align="right" sx={{ fontWeight: 600 }}>
                              {formatMoney(order.amount_paid)}
                            </TableCell>
                            <TableCell />
                          </TableRow>
                        </TableFooter>
                      </Table>
                    </TableContainer>
                  )}
                </SectionCard>

                {order.refunds.length > 0 ? (
                  <SectionCard title="Refunds">
                    <TableContainer sx={{ overflowX: 'auto' }}>
                      <Table size="small">
                        <TableHead>
                          <TableRow>
                            <TableCell>Date</TableCell>
                            <TableCell align="right">Amount</TableCell>
                            <TableCell>Reason</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {order.refunds.map((refund) => (
                            <TableRow key={refund.id}>
                              <TableCell>
                                {formatDate(refund.refunded_on)}
                              </TableCell>
                              <TableCell align="right">
                                -{formatMoney(refund.amount)}
                              </TableCell>
                              <TableCell
                                sx={{ whiteSpace: 'normal', minWidth: 200 }}>
                                {refund.reason || '—'}
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  </SectionCard>
                ) : null}

                <SectionCard title="History">
                  <CardContent>
                    <AuditTimeline entries={auditEntries} />
                  </CardContent>
                </SectionCard>
              </Stack>
            </Grid>

            <Grid size={{ xs: 12, md: 5 }}>
              <Stack gap={3}>
                <SectionCard title="Record a payment">
                  <CardContent>
                    <PaymentForm
                      orderId={order.id}
                      amountDue={order.amount_due}
                      today={today}
                    />
                  </CardContent>
                </SectionCard>

                <SectionCard title="Record a refund">
                  <CardContent>
                    <RefundForm
                      orderId={order.id}
                      amountPaid={order.amount_paid}
                      today={today}
                    />
                  </CardContent>
                </SectionCard>

                <SectionCard title="Order settings">
                  <CardContent>
                    <OrderSettingsForm order={order} />
                  </CardContent>
                </SectionCard>
              </Stack>
            </Grid>
          </Grid>
        </Stack>
      </Container>
    </>
  );
}
