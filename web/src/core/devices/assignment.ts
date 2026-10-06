export type DeviceAssignmentKind = 'gravity' | 'pressure' | 'temperature-control'

export interface AssignableDevice {
  id: string
  deviceType: string
  mdns?: string
  url?: string
  description?: string
}

/** Devices eligible for a batch assignment, independent of a product's UI labels. */
export function assignmentCandidates<T extends AssignableDevice>(
  devices: T[],
  kind: DeviceAssignmentKind
): T[] {
  if (kind === 'gravity') return devices.filter((device) => device.deviceType === 'gravitymon')
  if (kind === 'pressure') return devices.filter((device) => device.deviceType === 'pressuremon')
  return devices.filter(
    (device) => device.deviceType === 'chamber_controller' && Boolean(device.url)
  )
}

/** The most useful machine-visible location/name for a device. */
export function deviceEndpoint(device: AssignableDevice): string {
  return device.mdns || device.url || device.description || device.deviceType
}
