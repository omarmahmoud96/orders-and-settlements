'use client';

import { yupResolver } from '@hookform/resolvers/yup';
import { Alert, Button, Stack, TextField, Typography } from '@mui/material';
import { startTransition, useActionState, useEffect } from 'react';
import { useForm } from 'react-hook-form';

import { recordPaymentAction } from '@/lib/actions';
import { INITIAL_FORM_STATE } from '@/lib/form-state';
import { formatMoney } from '@/lib/money';
import { type PaymentFormValues, paymentSchema } from '@/schemas/paymentSchema';

import { SubmitButton } from './SubmitButton';

/**
 * Record a payment.
 *
 * RHF/Yup own client-side validation and field state; a valid submission is
 * turned into a `FormData` and handed to the Server Action's dispatcher
 * directly, so the browser still never talks to the API itself.
 */
export function PaymentForm({
  orderId,
  amountDue,
  today,
}: {
  orderId: number;
  amountDue: string;
  today: string;
}) {
  const [state, formAction, isPending] = useActionState(
    recordPaymentAction,
    INITIAL_FORM_STATE
  );
  const settled = Number.parseFloat(amountDue) <= 0;

  const {
    register,
    handleSubmit,
    setValue,
    reset,
    formState: { errors },
  } = useForm<PaymentFormValues>({
    resolver: yupResolver(paymentSchema),
    mode: 'onTouched',
    reValidateMode: 'onChange',
    defaultValues: { amount: '', paidOn: today, note: '' },
  });

  useEffect(() => {
    if (state.nonce) reset({ amount: '', paidOn: today, note: '' });
  }, [state.nonce, reset, today]);

  if (settled) {
    return (
      <Typography variant="body2" color="text.secondary">
        This order is settled in full. Nothing further can be recorded against
        it.
      </Typography>
    );
  }

  function onValid(values: PaymentFormValues) {
    const formData = new FormData();
    formData.set('order_id', String(orderId));
    formData.set('amount', values.amount);
    formData.set('paid_on', values.paidOn);
    formData.set('note', values.note ?? '');
    startTransition(() => formAction(formData));
  }

  return (
    <Stack component="form" gap={2} onSubmit={handleSubmit(onValid)} noValidate>
      {state.error ? (
        <Alert
          severity="error"
          action={
            state.maxAllowed && Number.parseFloat(state.maxAllowed) > 0 ? (
              <Button
                size="small"
                onClick={() =>
                  setValue('amount', state.maxAllowed as string, {
                    shouldValidate: true,
                  })
                }>
                Use {formatMoney(state.maxAllowed)}
              </Button>
            ) : undefined
          }>
          {state.error}
        </Alert>
      ) : null}

      {state.ok ? <Alert severity="success">Payment recorded.</Alert> : null}

      <Stack gap={0.5}>
        <TextField
          label="Amount"
          type="number"
          slotProps={{ htmlInput: { step: '0.01', min: '0.01' } }}
          {...register('amount')}
          error={Boolean(errors.amount)}
          helperText={errors.amount?.message}
        />
        <Stack direction="row" alignItems="center" gap={1}>
          <Typography variant="caption" color="text.secondary">
            {formatMoney(amountDue)} outstanding.
          </Typography>
          <Button
            size="small"
            onClick={() =>
              setValue('amount', amountDue, { shouldValidate: true })
            }>
            Pay in full
          </Button>
        </Stack>
      </Stack>

      <TextField
        label="Date received"
        type="date"
        slotProps={{ inputLabel: { shrink: true } }}
        {...register('paidOn')}
        error={Boolean(errors.paidOn)}
        helperText={errors.paidOn?.message}
      />

      <TextField
        label="Note (optional)"
        placeholder="Bank transfer reference"
        {...register('note')}
      />

      <SubmitButton loading={isPending} sx={{ alignSelf: 'flex-start' }}>
        Record payment
      </SubmitButton>
    </Stack>
  );
}
