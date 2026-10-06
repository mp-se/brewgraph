export type DetectedDeviceType =
  | 'kegmon'
  | 'chamber_controller'
  | 'gravitymon_gateway'
  | 'gravitymon'
  | 'pressuremon'
  | ''

/** Extract portable device identity fields from an untrusted status response. */
export function detectId(status: Record<string, unknown>): string {
  return typeof status.id === 'string' ? status.id : ''
}

export function detectMdns(status: Record<string, unknown>): string {
  return typeof status.mdns === 'string' ? status.mdns : ''
}

export function detectPlatform(status: Record<string, unknown>): string {
  return typeof status.platform === 'string' ? status.platform.split(' ')[0].toLowerCase() : ''
}

/** Infer device capability from the status fields exposed by its firmware. */
export function detectDeviceType(status: Record<string, unknown>): DetectedDeviceType {
  if ('scale_raw1' in status) return 'kegmon'
  if ('pid_mode' in status) return 'chamber_controller'
  if ('gravity_device' in status) return 'gravitymon_gateway'
  if ('gravity' in status) return 'gravitymon'
  if ('pressure' in status) return 'pressuremon'
  return ''
}
