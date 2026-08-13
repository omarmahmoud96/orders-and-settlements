/**
 * Shared shape for Server Action results.
 *
 * Kept out of `actions.ts` because a `"use server"` module may only export
 * async functions -- exporting the initial-state constant from there is a build
 * error.
 */

export interface FormState {
  ok?: boolean;
  error?: string;
  code?: string;
  fieldErrors?: Record<string, string[]>;
  /** Present on OVERPAYMENT / OVER_REFUND: the largest amount that would be accepted. */
  maxAllowed?: string;
  /**
   * Changes on every successful submission. Forms use it as a React `key` to
   * remount their inputs, which clears them without an effect that calls
   * setState (a cascading-render antipattern) or a stale success flag.
   */
  nonce?: number;
}

export const INITIAL_FORM_STATE: FormState = {};
