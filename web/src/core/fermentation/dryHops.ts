export interface StagedDryHop {
  name: string
  amount: number
  triggerHoursBefore: number
}

export interface DryHopPayload {
  name: string
  amount: number
  triggerMethod: 'hours_before_completion'
  triggerHoursBefore: number
  triggerGravity: null
}

/** Normalize dry-hop editor values into BrewGraph's canonical payload shape. */
export function dryHopsPayload(hops: readonly StagedDryHop[]): DryHopPayload[] {
  return hops.map((hop) => ({
    name: hop.name,
    amount: hop.amount,
    triggerMethod: 'hours_before_completion',
    triggerHoursBefore: Math.max(1, Math.round(hop.triggerHoursBefore)),
    triggerGravity: null
  }))
}
