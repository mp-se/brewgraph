export interface ValidationError {
  instancePath?: string
  keyword: string
  params: Record<string, unknown>
  message?: string
}

/** Render schema errors into a compact, deduplicated message suitable for a UI. */
export function validationErrorSummary(
  errors: ValidationError[] | null | undefined,
  maxReported = 5
): string {
  if (!errors?.length) return ''
  const seen = new Set<string>()
  const lines: string[] = []
  for (const error of errors) {
    const where = error.instancePath || '(document root)'
    let what: string
    switch (error.keyword) {
      case 'required':
        what = `is missing "${error.params.missingProperty}"`
        break
      case 'type':
        what = `should be ${error.params.type}`
        break
      case 'enum':
        what = `is not one of ${JSON.stringify(error.params.allowedValues)}`
        break
      case 'unevaluatedProperties':
      case 'additionalProperties':
        what = `has an unexpected field "${error.params.unevaluatedProperty ?? error.params.additionalProperty}"`
        break
      default:
        what = error.message ?? 'is invalid'
    }
    const line = `${where} ${what}`
    if (!seen.has(line)) lines.push(line)
    seen.add(line)
    if (lines.length >= maxReported) break
  }
  const more = errors.length - lines.length
  return lines.join('; ') + (more > 0 ? `; and ${more} more problem(s)` : '')
}
