import {
  Box,
  Card,
  CardContent,
  Container,
  Stack,
  Typography,
} from '@mui/material';
import Link from 'next/link';

import { SiteHeader } from '@/components/SiteHeader';
import { fetchCurrentUser } from '@/lib/queries';

import { NewOrderForm } from './NewOrderForm';

export const dynamic = 'force-dynamic';

function inDays(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

export default async function NewOrderPage() {
  const user = await fetchCurrentUser();

  return (
    <>
      <SiteHeader email={user.email} />
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Stack gap={3}>
          <Box>
            <Typography variant="h5" component="h1">
              New order
            </Typography>
            <Typography variant="body2" color="text.secondary">
              <Link href="/">Dashboard</Link> / New order
            </Typography>
          </Box>

          <Card variant="outlined">
            <CardContent>
              <NewOrderForm defaultDueDate={inDays(7)} />
            </CardContent>
          </Card>
        </Stack>
      </Container>
    </>
  );
}
