'use client';

import { yupResolver } from '@hookform/resolvers/yup';
import {
  Alert,
  Card,
  CardContent,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import Link from 'next/link';
import { startTransition, useActionState } from 'react';
import { useForm } from 'react-hook-form';

import { SubmitButton } from '@/components/SubmitButton';
import { loginAction } from '@/lib/actions';
import { INITIAL_FORM_STATE } from '@/lib/form-state';
import { type LoginFormValues, loginSchema } from '@/schemas/authSchema';

export default function LoginPage() {
  const [state, formAction, isPending] = useActionState(
    loginAction,
    INITIAL_FORM_STATE
  );

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: yupResolver(loginSchema),
    mode: 'onTouched',
    reValidateMode: 'onChange',
    defaultValues: { email: '', password: '' },
  });

  function onValid(values: LoginFormValues) {
    const formData = new FormData();
    formData.set('email', values.email);
    formData.set('password', values.password);
    startTransition(() => formAction(formData));
  }

  return (
    <Stack minHeight="100dvh" alignItems="center" justifyContent="center" p={3}>
      <Card sx={{ width: '100%', maxWidth: 400 }}>
        <CardContent>
          <Typography variant="h5">Log in</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2.5 }}>
            Sign in to see your orders and record payments.
          </Typography>

          <Stack
            component="form"
            gap={2}
            onSubmit={handleSubmit(onValid)}
            noValidate>
            {state.error ? <Alert severity="error">{state.error}</Alert> : null}

            <TextField
              label="Email"
              type="email"
              autoComplete="email"
              {...register('email')}
              error={Boolean(errors.email)}
              helperText={errors.email?.message}
            />

            <TextField
              label="Password"
              type="password"
              autoComplete="current-password"
              {...register('password')}
              error={Boolean(errors.password)}
              helperText={errors.password?.message}
            />

            <SubmitButton loading={isPending}>Log in</SubmitButton>
          </Stack>

          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            No account yet? <Link href="/register">Create one</Link>.
          </Typography>

          <Typography
            variant="caption"
            color="text.secondary"
            component="p"
            sx={{
              mt: 1.75,
              p: 1.25,
              border: '1px dashed',
              borderColor: 'divider',
              borderRadius: 1,
            }}>
            Seeded demo account: <strong>demo@example.com</strong> /{' '}
            <strong>demo-password-123</strong>
          </Typography>
        </CardContent>
      </Card>
    </Stack>
  );
}
