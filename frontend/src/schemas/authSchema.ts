import * as yup from 'yup';

export const loginSchema = yup.object({
  email: yup
    .string()
    .required('Enter your email.')
    .email('Enter a valid email.'),
  password: yup.string().required('Enter your password.'),
});

export type LoginFormValues = yup.InferType<typeof loginSchema>;

export const registerSchema = yup.object({
  name: yup.string().optional(),
  email: yup
    .string()
    .required('Enter your email.')
    .email('Enter a valid email.'),
  password: yup
    .string()
    .required('Enter a password.')
    .min(8, 'Password must be at least 8 characters.'),
});

export type RegisterFormValues = yup.InferType<typeof registerSchema>;
