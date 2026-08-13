'use client';

import { Button, type ButtonProps } from '@mui/material';
import { useFormStatus } from 'react-dom';

/**
 * Submit button that shows a spinner while the action is in flight.
 *
 * Pass `loading` explicitly for forms driven by RHF's `handleSubmit` (the
 * dispatcher is called manually, so there is no native form submission for
 * `useFormStatus` to observe). Left unset, it falls back to `useFormStatus`,
 * which works for the plain `<form action={...}>` forms (logout, delete,
 * export).
 */
export function SubmitButton({
  loading,
  variant = 'contained',
  children,
  ...props
}: ButtonProps & { loading?: boolean }) {
  const { pending } = useFormStatus();
  return (
    <Button
      type="submit"
      variant={variant}
      loading={loading ?? pending}
      {...props}>
      {children}
    </Button>
  );
}
