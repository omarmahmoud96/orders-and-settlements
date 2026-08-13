import * as yup from 'yup';

const AMOUNT_PATTERN = /^\d+(\.\d{1,2})?$/;

export const paymentSchema = yup.object({
  amount: yup
    .string()
    .required('Enter the payment amount.')
    .matches(AMOUNT_PATTERN, 'Enter a valid amount, e.g. 400.00.'),
  paidOn: yup.string().required('Enter the date the payment was made.'),
  note: yup.string().optional(),
});

export type PaymentFormValues = yup.InferType<typeof paymentSchema>;
