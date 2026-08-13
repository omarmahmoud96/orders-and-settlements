'use client';

import { yupResolver } from '@hookform/resolvers/yup';
import { Alert, Button, Stack, TextField, Typography } from '@mui/material';
import Link from 'next/link';
import { startTransition, useActionState } from 'react';
import { FormProvider, useForm } from 'react-hook-form';

import { LineItemsEditor } from '@/components/LineItemsEditor';
import { SubmitButton } from '@/components/SubmitButton';
import { createOrderAction } from '@/lib/actions';
import { INITIAL_FORM_STATE } from '@/lib/form-state';
import { type NewOrderFormValues, newOrderSchema } from '@/schemas/orderSchema';

export function NewOrderForm({ defaultDueDate }: { defaultDueDate: string }) {
  const [state, formAction, isPending] = useActionState(
    createOrderAction,
    INITIAL_FORM_STATE
  );

  const form = useForm<NewOrderFormValues>({
    resolver: yupResolver(newOrderSchema),
    mode: 'onTouched',
    reValidateMode: 'onChange',
    defaultValues: {
      customer: '',
      dueDate: defaultDueDate,
      lineItems: [{ description: '', quantity: 1, unitPrice: '' }],
    },
  });

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = form;

  function onValid(values: NewOrderFormValues) {
    const formData = new FormData();
    formData.set('customer', values.customer);
    formData.set('due_date', values.dueDate);
    formData.set(
      'line_items',
      JSON.stringify(
        values.lineItems.map((item) => ({
          description: item.description,
          quantity: item.quantity,
          unit_price: item.unitPrice,
        }))
      )
    );
    startTransition(() => formAction(formData));
  }

  return (
    <FormProvider {...form}>
      <Stack
        component="form"
        gap={3}
        onSubmit={handleSubmit(onValid)}
        noValidate>
        {state.error ? <Alert severity="error">{state.error}</Alert> : null}

        <Stack direction={{ xs: 'column', sm: 'row' }} gap={2}>
          <TextField
            fullWidth
            label="Customer"
            placeholder="Acme Corporation"
            {...register('customer')}
            error={Boolean(errors.customer)}
            helperText={errors.customer?.message}
          />
          <TextField
            fullWidth
            label="Due date"
            type="date"
            slotProps={{ inputLabel: { shrink: true } }}
            {...register('dueDate')}
            error={Boolean(errors.dueDate)}
            helperText={errors.dueDate?.message ?? 'When payment is expected.'}
          />
        </Stack>

        <Typography variant="h6">Line items</Typography>
        <LineItemsEditor />

        <Stack direction="row" gap={2}>
          <SubmitButton loading={isPending}>Create order</SubmitButton>
          <Button component={Link} href="/" variant="outlined">
            Cancel
          </Button>
        </Stack>
      </Stack>
    </FormProvider>
  );
}
