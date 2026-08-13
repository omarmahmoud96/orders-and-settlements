'use client';

import DeleteIcon from '@mui/icons-material/Delete';
import {
  Box,
  Button,
  Grid,
  IconButton,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useFieldArray, useFormContext, useWatch } from 'react-hook-form';

import { formatCents, parseCents, subtotalCents } from '@/lib/money';
import type { NewOrderFormValues } from '@/schemas/orderSchema';

/** The line item editor, wired to the `lineItems` field array of `NewOrderForm`. */
export function LineItemsEditor() {
  const {
    control,
    register,
    formState: { errors },
  } = useFormContext<NewOrderFormValues>();
  const { fields, append, remove } = useFieldArray({
    control,
    name: 'lineItems',
  });
  const lineItems = useWatch({ control, name: 'lineItems' }) ?? [];

  const subtotal = subtotalCents(
    lineItems.map((item) => ({
      quantity: item?.quantity ?? 0,
      unitPrice: item?.unitPrice ?? '',
    }))
  );

  return (
    <Box>
      {fields.map((field, index) => {
        const item = lineItems[index];
        const quantity = Number(item?.quantity);
        const unit = parseCents(item?.unitPrice ?? '');
        const lineTotal =
          Number.isFinite(quantity) && quantity > 0 && unit !== null
            ? Math.round(unit * quantity)
            : 0;
        const itemErrors = errors.lineItems?.[index];

        return (
          <Grid
            container
            spacing={1.5}
            key={field.id}
            alignItems="flex-start"
            sx={{ mb: 1.5 }}>
            <Grid size={{ xs: 12, sm: 'grow' }}>
              <TextField
                fullWidth
                label="Description"
                placeholder="Consulting day"
                {...register(`lineItems.${index}.description`)}
                error={Boolean(itemErrors?.description)}
                helperText={itemErrors?.description?.message}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 2 }}>
              <TextField
                fullWidth
                label="Quantity"
                type="number"
                slotProps={{ htmlInput: { min: 1, step: 1 } }}
                {...register(`lineItems.${index}.quantity`, {
                  valueAsNumber: true,
                })}
                error={Boolean(itemErrors?.quantity)}
                helperText={itemErrors?.quantity?.message}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 2.5 }}>
              <TextField
                fullWidth
                label="Unit price"
                type="number"
                placeholder="500.00"
                slotProps={{ htmlInput: { min: 0, step: '0.01' } }}
                {...register(`lineItems.${index}.unitPrice`)}
                error={Boolean(itemErrors?.unitPrice)}
                helperText={itemErrors?.unitPrice?.message}
              />
            </Grid>
            <Grid size={{ xs: 8, sm: 2 }}>
              <TextField
                fullWidth
                label="Line total"
                value={formatCents(lineTotal)}
                slotProps={{ htmlInput: { readOnly: true } }}
              />
            </Grid>
            <Grid size={{ xs: 4, sm: 'auto' }} sx={{ pt: 1 }}>
              <IconButton
                aria-label="Remove line item"
                onClick={() => remove(index)}
                disabled={fields.length === 1}>
                <DeleteIcon />
              </IconButton>
            </Grid>
          </Grid>
        );
      })}

      <Button
        type="button"
        onClick={() => append({ description: '', quantity: 1, unitPrice: '' })}>
        Add line item
      </Button>

      <Stack
        direction="row"
        justifyContent="flex-end"
        alignItems="baseline"
        gap={1.5}
        sx={{ borderTop: 1, borderColor: 'divider', mt: 2, pt: 2 }}>
        <Typography variant="body2" color="text.secondary">
          Order total
        </Typography>
        <Typography variant="h6">{formatCents(subtotal)}</Typography>
      </Stack>
    </Box>
  );
}
