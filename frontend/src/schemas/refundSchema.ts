import * as yup from 'yup';

const AMOUNT_PATTERN = /^\d+(\.\d{1,2})?$/;

export const refundSchema = yup.object({
  amount: yup
    .string()
    .required('Enter the refund amount.')
    .matches(AMOUNT_PATTERN, 'Enter a valid amount, e.g. 250.00.'),
  refundedOn: yup.string().required('Enter the date of the refund.'),
  reason: yup.string().optional(),
});

export type RefundFormValues = yup.InferType<typeof refundSchema>;
