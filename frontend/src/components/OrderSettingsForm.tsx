'use client';

import { yupResolver } from '@hookform/resolvers/yup';
import { Alert, Box, Stack, TextField, Typography } from '@mui/material';
import { startTransition, useActionState } from 'react';
import { useForm } from 'react-hook-form';

import { deleteOrderAction, updateOrderAction } from '@/lib/actions';
import { INITIAL_FORM_STATE } from '@/lib/form-state';
import type { OrderDetail } from '@/lib/types';
import {
  type OrderSettingsFormValues,
  orderSettingsSchema,
} from '@/schemas/orderSchema';

import { SubmitButton } from './SubmitButton';

/**
 * Edit the fields that stay editable for an order's whole life.
 *
 * Line items are not among them once a settlement exists -- see the note this
 * component renders, and `update_order` in the backend services module for why.
 */
export function OrderSettingsForm({ order }: { order: OrderDetail }) {
  const [state, formAction, isPending] = useActionState(
    updateOrderAction,
    INITIAL_FORM_STATE
  );
  const [deleteState, deleteAction, isDeleting] = useActionState(
    deleteOrderAction,
    INITIAL_FORM_STATE
  );

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<OrderSettingsFormValues>({
    resolver: yupResolver(orderSettingsSchema),
    mode: 'onTouched',
    reValidateMode: 'onChange',
    defaultValues: { customer: order.customer, dueDate: order.due_date },
  });

  function onValid(values: OrderSettingsFormValues) {
    const formData = new FormData();
    formData.set('order_id', String(order.id));
    formData.set('customer', values.customer);
    formData.set('due_date', values.dueDate);
    startTransition(() => formAction(formData));
  }

  return (
    <>
      <Stack
        component="form"
        gap={2}
        onSubmit={handleSubmit(onValid)}
        noValidate>
        {state.error ? <Alert severity="error">{state.error}</Alert> : null}
        {state.ok ? <Alert severity="success">Order updated.</Alert> : null}

        <TextField
          label="Customer"
          {...register('customer')}
          error={Boolean(errors.customer)}
          helperText={errors.customer?.message}
        />

        <TextField
          label="Due date"
          type="date"
          slotProps={{ inputLabel: { shrink: true } }}
          {...register('dueDate')}
          error={Boolean(errors.dueDate)}
          helperText={errors.dueDate?.message}
        />

        <SubmitButton loading={isPending} sx={{ alignSelf: 'flex-start' }}>
          Save changes
        </SubmitButton>
      </Stack>

      {order.is_locked ? (
        <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
          This order has settlements recorded against it, so its line items and
          total are locked. Editable: {order.editable_fields.join(', ')}.
        </Typography>
      ) : (
        <Box component="form" action={deleteAction} sx={{ mt: 2 }}>
          <input type="hidden" name="order_id" value={order.id} />
          {deleteState.error ? (
            <Alert severity="error" sx={{ mb: 1 }}>
              {deleteState.error}
            </Alert>
          ) : null}
          <SubmitButton loading={isDeleting} color="error" variant="outlined">
            Delete order
          </SubmitButton>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            Available until the first payment is recorded.
          </Typography>
        </Box>
      )}
    </>
  );
}
