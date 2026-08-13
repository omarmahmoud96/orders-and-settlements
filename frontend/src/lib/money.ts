/** Money on the client: display and live-subtotal arithmetic in integer cents. */

/** Parse a decimal string like "1234.56" into an integer number of cents. */
export function parseCents(value: string | number): number | null {
  const raw = String(value ?? '').trim();
  if (raw === '') return null;
  if (!/^-?\d*(\.\d*)?$/.test(raw)) return null;

  const negative = raw.startsWith('-');
  const [whole = '0', fraction = ''] = raw.replace('-', '').split('.');
  const cents =
    Number(whole || '0') * 100 + Number(`${fraction}00`.slice(0, 2) || '0');
  if (!Number.isFinite(cents)) return null;
  return negative ? -cents : cents;
}

/** Render integer cents as a plain decimal string, e.g. 100050 -> "1000.50". */
export function centsToDecimalString(cents: number): string {
  const negative = cents < 0;
  const absolute = Math.abs(Math.round(cents));
  const value = `${Math.floor(absolute / 100)}.${String(absolute % 100).padStart(2, '0')}`;
  return negative ? `-${value}` : value;
}

/** Format an amount for display: "1000.50" -> "$1,000.50". */
export function formatMoney(value: string | number): string {
  const amount = typeof value === 'number' ? value : Number.parseFloat(value);
  if (!Number.isFinite(amount)) return String(value);
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(amount);
}

/** Format integer cents for display. */
export function formatCents(cents: number): string {
  return formatMoney(centsToDecimalString(cents));
}

/** Subtotal of a set of line item inputs, in integer cents. */
export function subtotalCents(
  items: { quantity: string | number; unitPrice: string }[]
): number {
  return items.reduce((sum, item) => {
    const quantity = Number(item.quantity);
    const unit = parseCents(item.unitPrice);
    if (!Number.isFinite(quantity) || quantity < 0 || unit === null) return sum;
    return sum + Math.round(unit * quantity);
  }, 0);
}
