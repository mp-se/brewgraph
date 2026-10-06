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

import { ref, computed, watch } from 'vue'
import type { Ref, ComputedRef } from 'vue'

export function usePagination<T>(items: Ref<T[] | null> | ComputedRef<T[]>, pageSize: number) {
  const currentPage = ref(1)

  const totalPages = computed(() => {
    const count = items.value?.length ?? 0
    return Math.max(1, Math.ceil(count / pageSize))
  })

  const pagedItems = computed(() => {
    const list = items.value ?? []
    const start = (currentPage.value - 1) * pageSize
    return list.slice(start, start + pageSize)
  })

  function goToPage(page: number) {
    currentPage.value = Math.max(1, Math.min(page, totalPages.value))
  }

  function resetPage() {
    currentPage.value = 1
  }

  watch(totalPages, (pages) => {
    if (currentPage.value > pages) currentPage.value = pages
  })

  return { currentPage, totalPages, pagedItems, goToPage, resetPage }
}
