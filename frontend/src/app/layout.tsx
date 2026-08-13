import type { Metadata } from 'next';

import { Body } from './Body';

export const metadata: Metadata = {
  title: 'Orders & Settlements',
  description:
    'Create orders with line items, record payments, and track what is still owed.',
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <Body>{children}</Body>
      </body>
    </html>
  );
}
