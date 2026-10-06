/** Framework-neutral brewing calculations and unit conversions. */

export function gravityToPlato(specificGravity: number): number {
  return (
    135.997 * specificGravity ** 3 -
    630.272 * specificGravity ** 2 +
    1111.14 * specificGravity -
    616.868
  )
}

export function platoToGravity(plato: number): number {
  return 1 + plato / (258.6 - 227.1 * (plato / 258.2))
}

export function tempToF(celsius: number): number {
  return celsius * 1.8 + 32
}

export function tempToC(fahrenheit: number): number {
  return (fahrenheit - 32) / 1.8
}

export function pressureToBAR(psi: number): number {
  return psi * 0.0689475729
}

export function pressureToKPA(psi: number): number {
  return psi * 6.89475729
}

export function pressureFromBAR(bar: number): number {
  return bar / 0.0689475729
}

export function pressureFromKPA(kilopascals: number): number {
  return kilopascals / 6.8947572932
}

export function volumeCLtoUSOZ(centiliters: number): number {
  return centiliters * 0.338140225
}

export function volumeCLtoUKOZ(centiliters: number): number {
  return centiliters * 0.35119572
}

export function volumeLtoUSGallon(liters: number): number {
  return liters * 0.264172052
}

export function volumeLtoUKGallon(liters: number): number {
  return liters * 0.2199692483
}

export function volumeLtoCL(liters: number): number {
  return liters * 100
}

export function volumeLtoUSFlOz(liters: number): number {
  return liters * 33.8140226
}

export function volumeLtoUKPint(liters: number): number {
  return liters * 1.7597539864
}

export function volumeUSGallonToL(gallons: number): number {
  return gallons / 0.264172052
}

export function volumeUKGallonToL(gallons: number): number {
  return gallons / 0.2199692483
}

export function volumeUSFlOzToL(ounces: number): number {
  return ounces / 33.8140226
}

export function volumeUKPintToL(pints: number): number {
  return pints / 1.7597539864
}

export function volumeCLtoL(centiliters: number): number {
  return centiliters / 100
}

export function roundValue(value: number | null | undefined, decimals = 1): number {
  if (value === null || value === undefined) return 0
  return Number.parseFloat(value.toFixed(decimals))
}

/** Alcohol by volume (%) from original and final specific gravity. */
export function abv(originalGravity: number, finalGravity: number): number {
  return (
    Math.round(
      ((76.08 * (originalGravity - finalGravity)) / (1.775 - originalGravity)) *
        (finalGravity / 0.794) *
        100
    ) / 100
  )
}
