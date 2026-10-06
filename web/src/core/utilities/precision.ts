/** Correctly-rounded numeric input step for a decimal precision. */
export function decimalStep(decimals: number): number {
  return Number(`1e-${decimals}`)
}

export function decimalPrecision(
  quantity: string,
  configured: Record<string, number> | null | undefined,
  fallback: Record<string, number>
): number | undefined {
  return configured?.[quantity] ?? fallback[quantity]
}
