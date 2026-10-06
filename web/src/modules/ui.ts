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

import { computed, ref } from 'vue'
import { logDebug } from '@/ui'
import { sortRecords } from '@brewgraph/core'

type SortType = 'str' | 'num' | 'date'

interface SortingState {
  column: string
  type: SortType
  order: boolean
}

const sorting = ref<SortingState>({ column: 'name', type: 'str', order: false })

export const sortedIconClass = computed(() => 'sort_by_alpha')

export function setSortingDefault(column: string, type: SortType, order: boolean): void {
  logDebug('ui.setSortingDefault()', column, type, order)
  sorting.value = { column, type, order }
}

export function sortedClass(column: string): string {
  if (column == sorting.value.column) return 'text-primary'
  return ''
}

export function sortList(list: Record<string, unknown>[], column: string, type: SortType): void {
  logDebug('ui.sortList()', column, type)
  sorting.value.column = column
  sorting.value.type = type
  sorting.value.order = !sorting.value.order
  applySortList(list)
}

export function applySortList(list: Record<string, unknown>[]): void {
  logDebug('ui.applySortList()', sorting.value.column, sorting.value.type, sorting.value.order)
  sortRecords(list, sorting.value)
}
