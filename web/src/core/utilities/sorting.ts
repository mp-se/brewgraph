export type SortType = 'str' | 'num' | 'date'

export interface SortState {
  column: string
  type: SortType
  /** `true` means ascending order. */
  order: boolean
}

/** Sort records in place using the shared list-table ordering semantics. */
export function sortRecords(records: Record<string, unknown>[], state: SortState): void {
  const { column, type, order } = state
  records.sort((a, b) => {
    const valueA = a[column]
    const valueB = b[column]
    if (valueA === undefined || valueA === null) return order ? 1 : -1
    if (valueB === undefined || valueB === null) return order ? -1 : 1
    if (type === 'str') {
      return order
        ? String(valueA).localeCompare(String(valueB))
        : String(valueB).localeCompare(String(valueA))
    }
    if (type === 'date') {
      const dateA = new Date(valueA as string).getTime()
      const dateB = new Date(valueB as string).getTime()
      return order ? dateA - dateB : dateB - dateA
    }
    return order
      ? (valueA as number) - (valueB as number)
      : (valueB as number) - (valueA as number)
  })
}
