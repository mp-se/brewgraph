/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 * BrewGraph — https://github.com/mp-se/brewgraph
 *
 * This file is part of BrewGraph. For open source use it is licensed under
 * the GNU General Public License v3.0. For commercial use without source
 * disclosure, a separate Commercial License is required.
 * See LICENSE for details.
 */

import { ref, computed } from 'vue'
import { logDebug } from '@/ui'
import { sortRecords, type SortType } from '@brewgraph/core'

interface SortingState {
  column: string
  type: SortType
  order: boolean
}

export function useSortableList(
  initialColumn = 'name',
  initialType: SortType = 'str',
  initialOrder = true
) {
  const sorting = ref<SortingState>({
    column: initialColumn,
    type: initialType,
    order: initialOrder
  })

  const sortedIconClass = computed(() => {
    if (sorting.value.type === 'str') {
      return sorting.value.order ? 'sort_by_alpha' : 'sort_by_alpha'
    }
    return sorting.value.order ? 'format_list_numbered' : 'format_list_numbered'
  })

  function getSortedClass(column: string): string {
    if (column === sorting.value.column) return 'text-primary text-weight-bold'
    return ''
  }

  function setSortingDefault(column: string, type: SortType, order: boolean): void {
    logDebug('useSortableList: setSortingDefault()', column, type, order)
    sorting.value = { column, type, order }
  }

  function sortList(list: Record<string, unknown>[], column: string, type: SortType): void {
    logDebug('useSortableList: sortList()', column, type)

    if (sorting.value.column === column) {
      sorting.value.order = !sorting.value.order
    } else {
      sorting.value.column = column
      sorting.value.type = type
      sorting.value.order = true
    }

    applySortList(list)
  }

  function applySortList(list: Record<string, unknown>[]): void {
    if (!list || !Array.isArray(list) || list.length === 0) return

    logDebug(
      'useSortableList: applySortList()',
      sorting.value.column,
      sorting.value.type,
      sorting.value.order
    )

    sortRecords(list, sorting.value)
  }

  return { sorting, sortedIconClass, getSortedClass, setSortingDefault, sortList, applySortList }
}
