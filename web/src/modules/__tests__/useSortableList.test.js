/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 */

import { describe, it, expect, vi } from 'vitest'
import { useSortableList } from '@/modules/useSortableList'

vi.mock('@/ui', () => ({
  logDebug: vi.fn()
}))

describe('useSortableList', () => {
  describe('applySortList', () => {
    it('returns early for null list', () => {
      const { applySortList } = useSortableList()
      expect(() => applySortList(null)).not.toThrow()
    })

    it('returns early for empty list', () => {
      const { applySortList } = useSortableList()
      const list = []
      applySortList(list)
      expect(list).toEqual([])
    })

    it('returns early for non-array', () => {
      const { applySortList } = useSortableList()
      expect(() => applySortList('not-an-array')).not.toThrow()
    })

    it('sorts strings ascending by default', () => {
      const { applySortList } = useSortableList('name', 'str', true)
      const list = [{ name: 'Charlie' }, { name: 'Alice' }, { name: 'Bob' }]
      applySortList(list)
      expect(list[0].name).toBe('Alice')
      expect(list[1].name).toBe('Bob')
      expect(list[2].name).toBe('Charlie')
    })

    it('sorts strings descending when order=false', () => {
      const { applySortList } = useSortableList('name', 'str', false)
      const list = [{ name: 'Charlie' }, { name: 'Alice' }, { name: 'Bob' }]
      applySortList(list)
      expect(list[0].name).toBe('Charlie')
      expect(list[2].name).toBe('Alice')
    })

    it('sorts numbers ascending', () => {
      const { applySortList } = useSortableList('count', 'num', true)
      const list = [{ count: 30 }, { count: 10 }, { count: 20 }]
      applySortList(list)
      expect(list[0].count).toBe(10)
      expect(list[2].count).toBe(30)
    })

    it('sorts numbers descending', () => {
      const { applySortList } = useSortableList('count', 'num', false)
      const list = [{ count: 30 }, { count: 10 }, { count: 20 }]
      applySortList(list)
      expect(list[0].count).toBe(30)
      expect(list[2].count).toBe(10)
    })

    it('sorts dates ascending', () => {
      const { applySortList } = useSortableList('date', 'date', true)
      const list = [{ date: '2026-03-01' }, { date: '2026-01-01' }, { date: '2026-02-01' }]
      applySortList(list)
      expect(list[0].date).toBe('2026-01-01')
      expect(list[2].date).toBe('2026-03-01')
    })

    it('sorts dates descending', () => {
      const { applySortList } = useSortableList('date', 'date', false)
      const list = [{ date: '2026-03-01' }, { date: '2026-01-01' }, { date: '2026-02-01' }]
      applySortList(list)
      expect(list[0].date).toBe('2026-03-01')
    })

    it('places nulls last when ascending', () => {
      const { applySortList } = useSortableList('name', 'str', true)
      const list = [{ name: null }, { name: 'Alice' }, { name: undefined }]
      applySortList(list)
      // Alice should be first
      expect(list[0].name).toBe('Alice')
    })

    it('places nulls first when descending', () => {
      const { applySortList } = useSortableList('name', 'str', false)
      const list = [{ name: 'Alice' }, { name: null }]
      applySortList(list)
      expect(list[0].name).toBeNull()
    })
  })

  describe('sortList', () => {
    it('toggles order when same column is clicked', () => {
      const { sortList, sorting } = useSortableList('name', 'str', true)
      const list = [{ name: 'B' }, { name: 'A' }]
      expect(sorting.value.order).toBe(true)
      sortList(list, 'name', 'str')
      expect(sorting.value.order).toBe(false)
    })

    it('resets order to true when different column is clicked', () => {
      const { sortList, sorting } = useSortableList('name', 'str', false)
      const list = [
        { count: 2, name: 'B' },
        { count: 1, name: 'A' }
      ]
      sortList(list, 'count', 'num')
      expect(sorting.value.order).toBe(true)
      expect(sorting.value.column).toBe('count')
    })

    it('applies sort after toggling', () => {
      const { sortList } = useSortableList('name', 'str', true)
      const list = [{ name: 'Charlie' }, { name: 'Alice' }]
      sortList(list, 'name', 'str') // toggles to false (descending)
      expect(list[0].name).toBe('Charlie')
    })
  })

  describe('setSortingDefault', () => {
    it('sets column, type, and order', () => {
      const { setSortingDefault, sorting } = useSortableList()
      setSortingDefault('desc', 'str', false)
      expect(sorting.value.column).toBe('desc')
      expect(sorting.value.type).toBe('str')
      expect(sorting.value.order).toBe(false)
    })
  })

  describe('getSortedClass', () => {
    it('returns text-primary class for active column', () => {
      const { getSortedClass } = useSortableList('name')
      expect(getSortedClass('name')).toBe('text-primary text-weight-bold')
    })

    it('returns empty string for inactive column', () => {
      const { getSortedClass } = useSortableList('name')
      expect(getSortedClass('other')).toBeFalsy()
    })
  })

  describe('sortedIconClass', () => {
    it('returns alpha-down icon for str asc', () => {
      const { sortedIconClass } = useSortableList('name', 'str', true)
      expect(sortedIconClass.value).toBe('sort_by_alpha')
    })

    it('returns alpha-up icon for str desc', () => {
      const { sortedIconClass } = useSortableList('name', 'str', false)
      expect(sortedIconClass.value).toBe('sort_by_alpha')
    })

    it('returns numeric-down icon for num asc', () => {
      const { sortedIconClass } = useSortableList('count', 'num', true)
      expect(sortedIconClass.value).toBe('format_list_numbered')
    })

    it('returns numeric-up icon for num desc', () => {
      const { sortedIconClass } = useSortableList('count', 'num', false)
      expect(sortedIconClass.value).toBe('format_list_numbered')
    })
  })

  describe('default parameters', () => {
    it('uses name, str, true as defaults', () => {
      const { sorting } = useSortableList()
      expect(sorting.value.column).toBe('name')
      expect(sorting.value.type).toBe('str')
      expect(sorting.value.order).toBe(true)
    })
  })
})
