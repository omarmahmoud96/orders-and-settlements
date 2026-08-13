'use client';

import { yupResolver } from '@hookform/resolvers/yup';
import { Alert, Button, Stack, TextField, Typography } from '@mui/material';
import { startTransition, useActionState, useEffect } from 'react';
import { useForm } from 'react-hook-form';

import { recordRefundAction } from '@/lib/actions';
import { INITIAL_FORM_STATE } from '@/lib/form-state';
import { formatMoney } from '@/lib/money';
import { type RefundFormValues, refundSchema } from '@/schemas/refundSchema';

import { SubmitButton } from './SubmitButton';

/** Record a refund (stretch goal). Cannot exceed the net amount received. */
export function RefundForm({
  orderId,
  amountPaid,
  today,
}: {
  orderId: number;
  amountPaid: string;
  today: string;
}) {
  const [state, formAction, isPending] = useActionState(
    recordRefundAction,
    INITIAL_FORM_STATE
  );

  const {
    register,
    handleSubmit,
    setValue,
    reset,
    formState: { errors },
  } = useForm<RefundFormValues>({
    resolver: yupResolver(refundSchema),
    mode: 'onTouched',
    reValidateMode: 'onChange',
    defaultValues: { amount: '', refundedOn: today, reason: '' },
  });

  useEffect(() => {
    if (state.nonce) reset({ amount: '', refundedOn: today, reason: '' });
  }, [state.nonce, reset, today]);

  if (Number.parseFloat(amountPaid) <= 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        Nothing has been received on this order, so there is nothing to refund.
      </Typography>
    );
  }

  function onValid(values: RefundFormValues) {
    const formData = new FormData();
    formData.set('order_id', String(orderId));
    formData.set('amount', values.amount);
    formData.set('refunded_on', values.refundedOn);
    formData.set('reason', values.reason ?? '');
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

      {state.ok ? <Alert severity="success">Refund recorded.</Alert> : null}

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
            {formatMoney(amountPaid)} received so far.
          </Typography>
          <Button
            size="small"
            onClick={() =>
              setValue('amount', amountPaid, { shouldValidate: true })
            }>
            Refund all
          </Button>
        </Stack>
      </Stack>

      <TextField
        label="Date refunded"
        type="date"
        slotProps={{ inputLabel: { shrink: true } }}
        {...register('refundedOn')}
        error={Boolean(errors.refundedOn)}
        helperText={errors.refundedOn?.message}
      />

      <TextField
        label="Reason (optional)"
        placeholder="Two units returned damaged"
        {...register('reason')}
      />

      <SubmitButton loading={isPending} sx={{ alignSelf: 'flex-start' }}>
        Record refund
      </SubmitButton>
    </Stack>
  );
}
