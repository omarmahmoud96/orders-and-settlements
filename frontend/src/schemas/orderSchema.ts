import * as yup from 'yup';

const PRICE_PATTERN = /^\d+(\.\d{1,2})?$/;

export const orderSettingsSchema = yup.object({
  customer: yup.string().required('Enter the customer name.'),
  dueDate: yup.string().required('Enter a due date.'),
});

export type OrderSettingsFormValues = yup.InferType<typeof orderSettingsSchema>;

export const lineItemSchema = yup.object({
  description: yup.string().required('Enter a description.'),
  quantity: yup
    .number()
    .typeError('Enter a quantity.')
    .required('Enter a quantity.')
    .integer('Quantity must be a whole number.')
    .min(1, 'Quantity must be at least 1.'),
  unitPrice: yup
    .string()
    .required('Enter a unit price.')
    .matches(PRICE_PATTERN, 'Enter a valid price, e.g. 500.00.'),
});

export const newOrderSchema = yup.object({
  customer: yup.string().required('Enter the customer name.'),
  dueDate: yup.string().required('Enter a due date.'),
  lineItems: yup
    .array()
    .of(lineItemSchema)
    .min(1, 'Add at least one line item before saving the order.')
    .required(),
});

export type NewOrderFormValues = yup.InferType<typeof newOrderSchema>;
