'use client';

import { AppRouterCacheProvider } from '@mui/material-nextjs/v13-appRouter';
import type { ReactNode } from 'react';

import { ThemeProvider } from '@/providers/themeProvider';

export function Body({ children }: { children: ReactNode }) {
  return (
    <AppRouterCacheProvider>
      <ThemeProvider>{children}</ThemeProvider>
    </AppRouterCacheProvider>
  );
}
