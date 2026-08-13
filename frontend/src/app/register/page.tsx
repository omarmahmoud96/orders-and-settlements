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
import { registerAction } from '@/lib/actions';
import { INITIAL_FORM_STATE } from '@/lib/form-state';
import { type RegisterFormValues, registerSchema } from '@/schemas/authSchema';

export default function RegisterPage() {
  const [state, formAction, isPending] = useActionState(
    registerAction,
    INITIAL_FORM_STATE
  );
  const passwordErrors = state.fieldErrors?.password ?? [];
  const emailErrors = state.fieldErrors?.email ?? [];

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterFormValues>({
    resolver: yupResolver(registerSchema),
    mode: 'onTouched',
    reValidateMode: 'onChange',
    defaultValues: { name: '', email: '', password: '' },
  });

  function onValid(values: RegisterFormValues) {
    const formData = new FormData();
    formData.set('name', values.name ?? '');
    formData.set('email', values.email);
    formData.set('password', values.password);
    startTransition(() => formAction(formData));
  }

  return (
    <Stack minHeight="100dvh" alignItems="center" justifyContent="center" p={3}>
      <Card sx={{ width: '100%', maxWidth: 400 }}>
        <CardContent>
          <Typography variant="h5">Create an account</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2.5 }}>
            Your orders and payments are visible only to you.
          </Typography>

          <Stack
            component="form"
            gap={2}
            onSubmit={handleSubmit(onValid)}
            noValidate>
            {state.error ? <Alert severity="error">{state.error}</Alert> : null}

            <TextField
              label="Name (optional)"
              autoComplete="name"
              {...register('name')}
            />

            <TextField
              label="Email"
              type="email"
              autoComplete="email"
              {...register('email')}
              error={Boolean(errors.email) || emailErrors.length > 0}
              helperText={errors.email?.message ?? emailErrors.join(' ')}
            />

            <TextField
              label="Password"
              type="password"
              autoComplete="new-password"
              {...register('password')}
              error={Boolean(errors.password) || passwordErrors.length > 0}
              helperText={
                errors.password?.message ??
                (passwordErrors.length > 0
                  ? passwordErrors.join(' ')
                  : 'At least 8 characters, and not entirely numeric.')
              }
            />

            <SubmitButton loading={isPending}>Create account</SubmitButton>
          </Stack>

          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            Already have an account? <Link href="/login">Log in</Link>.
          </Typography>
        </CardContent>
      </Card>
    </Stack>
  );
}
