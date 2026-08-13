'use client';

import { Button, type ButtonProps } from '@mui/material';
import Link from 'next/link';

/**
 * `Button` that navigates via `next/link`.
 *
 * `component={Link}` passes a function reference as a prop, which Server
 * Components cannot hand to a Client Component (MUI's `Button`) directly, so
 * this small wrapper keeps the composition inside a Client Component.
 */
export function LinkButton({ href, ...props }: ButtonProps & { href: string }) {
  return <Button component={Link} href={href} {...props} />;
}
