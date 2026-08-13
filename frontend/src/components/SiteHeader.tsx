'use client';

import { AppBar, Box, Toolbar, Typography } from '@mui/material';
import Link from 'next/link';

import { logoutAction } from '@/lib/actions';

import { SubmitButton } from './SubmitButton';

export function SiteHeader({ email }: { email?: string }) {
  return (
    <AppBar
      position="static"
      color="inherit"
      elevation={0}
      sx={{ borderBottom: 1, borderColor: 'divider' }}>
      <Toolbar sx={{ gap: 2.5 }}>
        <Typography
          component={Link}
          href="/"
          variant="subtitle1"
          fontWeight={650}
          color="text.primary"
          sx={{ textDecoration: 'none' }}>
          Orders &amp; Settlements
        </Typography>
        <Box flex={1} />
        {email ? (
          <Typography variant="body2" color="text.secondary">
            {email}
          </Typography>
        ) : null}
        <Box component="form" action={logoutAction}>
          <SubmitButton variant="outlined" size="small">
            Log out
          </SubmitButton>
        </Box>
      </Toolbar>
    </AppBar>
  );
}
