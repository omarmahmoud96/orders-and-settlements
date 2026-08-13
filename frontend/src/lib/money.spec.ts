import { describe, expect, it } from 'vitest';

import {
  centsToDecimalString,
  formatMoney,
  parseCents,
  subtotalCents,
} from './money';

describe('parseCents', () => {
  it('parses plain decimal strings', () => {
    expect(parseCents('1000.50')).toBe(100050);
    expect(parseCents('0.01')).toBe(1);
    expect(parseCents('500')).toBe(50000);
    expect(parseCents('249.99')).toBe(24999);
  });

  it('pads and truncates the fractional part', () => {
    expect(parseCents('1.5')).toBe(150);
    expect(parseCents('1.')).toBe(100);
  });

  it('rejects anything that is not a decimal number', () => {
    expect(parseCents('')).toBeNull();
    expect(parseCents('abc')).toBeNull();
    expect(parseCents('1.2.3')).toBeNull();
  });
});

describe('centsToDecimalString', () => {
  it('always renders two places', () => {
    expect(centsToDecimalString(100050)).toBe('1000.50');
    expect(centsToDecimalString(1)).toBe('0.01');
    expect(centsToDecimalString(0)).toBe('0.00');
    expect(centsToDecimalString(-2500)).toBe('-25.00');
  });
});

describe('subtotalCents', () => {
  it("computes the assignment's sample order", () => {
    expect(subtotalCents([{ quantity: 2, unitPrice: '500.00' }])).toBe(100000);
  });

  it('stays exact where floating point would drift', () => {
    // 3 x 0.10 is 0.30, not 0.30000000000000004
    const cents = subtotalCents([{ quantity: 3, unitPrice: '0.10' }]);
    expect(cents).toBe(30);
    expect(centsToDecimalString(cents)).toBe('0.30');

    // 10 x 249.99
    expect(subtotalCents([{ quantity: 10, unitPrice: '249.99' }])).toBe(249990);
  });

  it('sums several lines', () => {
    expect(
      subtotalCents([
        { quantity: 2, unitPrice: '500.00' },
        { quantity: 3, unitPrice: '42.50' },
        { quantity: 1, unitPrice: '99.99' },
      ])
    ).toBe(122749);
  });

  it('ignores incomplete rows instead of producing NaN', () => {
    expect(
      subtotalCents([
        { quantity: 2, unitPrice: '500.00' },
        { quantity: '', unitPrice: '' },
        { quantity: 1, unitPrice: 'abc' },
      ])
    ).toBe(100000);
  });
});

describe('formatMoney', () => {
  it('formats decimal strings from the API', () => {
    expect(formatMoney('1000.00')).toBe('$1,000.00');
    expect(formatMoney('0.00')).toBe('$0.00');
    expect(formatMoney('2499.90')).toBe('$2,499.90');
  });

  it('passes through values it cannot parse', () => {
    expect(formatMoney('n/a')).toBe('n/a');
  });
});
